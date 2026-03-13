# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Orchestration logic for runbook verification and LLM correction loops.
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from opentelemetry import metrics, trace

from agent.core.logger import get_logger
from agent.core.telemetry import get_tracer
from agent.core.ai.service import AIService
from agent.core.implement.verifier import RunbookVerifier, VerificationError

logger = get_logger(__name__)
tracer = get_tracer()
meter = metrics.get_meter(__name__)

# Define telemetry counters
success_counter = meter.create_counter(
    "verification.successes",
    description="Number of successful runbook verifications",
)
failure_counter = meter.create_counter(
    "verification.failures",
    description="Number of failed runbook verifications",
)
rewrite_counter = meter.create_counter(
    "verification.rewrite_cycles",
    description="Number of rewrite cycles attempted",
)

class RunbookStep(BaseModel):
    """Represents a single step in a runbook."""
    action: str = Field(..., description="Action to perform, e.g., 'MODIFY'")
    path: Optional[str] = Field(None, description="Target file path")
    search: Optional[str] = Field(None, description="Search block for MODIFY actions")
    replace: Optional[str] = Field(None, description="Replacement block for MODIFY actions")
    content: Optional[str] = Field(None, description="Content for NEW actions")


class VerificationOrchestrator:
    """
    Manages the dry-run and rewrite lifecycle for runbooks.
    """

    def __init__(self, verifier: RunbookVerifier, ai_service: AIService, max_retries: int = 3):
        """
        Initialize the orchestrator.

        :param verifier: The verifier instance.
        :param ai_service: The AI service for rewrites.
        :param max_retries: Maximum number of correction attempts.
        """
        self.verifier = verifier
        self.ai_service = ai_service
        self.max_retries = max_retries

    def verify_and_correct(self, runbook_steps: List[RunbookStep]) -> Tuple[bool, List[RunbookStep]]:
        """
        Verify all steps and attempt to correct them via LLM if they fail.

        :param runbook_steps: List of parsed runbook steps.
        :return: (Final success status, Final steps)
        """
        current_steps = runbook_steps
        attempts = 0

        with tracer.start_as_current_span("verify_and_correct") as span:
            span.set_attribute("max_retries", self.max_retries)
            
            while attempts <= self.max_retries:
                errors = self._verify_all_steps(current_steps)
                
                if not errors:
                    logger.info(f"Runbook verified successfully after {attempts} rewrites.")
                    span.set_attribute("final_status", "success")
                    span.set_attribute("attempts", attempts)
                    success_counter.add(1)
                    return True, current_steps
                
                if attempts == self.max_retries:
                    logger.error("Reached maximum rewrite attempts for runbook.")
                    break
                    
                attempts += 1
                logger.info(f"Attempting runbook rewrite cycle {attempts}/{self.max_retries}")
                rewrite_counter.add(1)
                
                current_steps = self._request_rewrite(current_steps, errors)
                if not current_steps:
                    break

            span.set_attribute("final_status", "failure")
            span.set_attribute("attempts", attempts)
            failure_counter.add(1)
            return False, current_steps

    def _verify_all_steps(self, steps: List[RunbookStep]) -> List[VerificationError]:
        """
        Check all steps against the verifier.

        :param steps: Steps to check.
        :return: List of verification errors.
        """
        errors = []
        for step in steps:
            if step.action == "MODIFY":
                if step.path and step.search:
                    success, error = self.verifier.verify_block(step.path, step.search)
                    if error:
                        errors.append(error)
        return errors

    def _request_rewrite(self, steps: List[RunbookStep], errors: List[VerificationError]) -> Optional[List[RunbookStep]]:
        """
        Prompt the LLM to fix the specific failed blocks.

        :param steps: Current steps.
        :param errors: Errors found.
        :return: Corrected steps or None if failure.
        """
        try:
            prompt = "The following runbook steps failed verification. Please fix the search blocks to exactly match the file context:\\n"
            for err in errors:
                prompt += f"\\nFile: {err.file_path}\\nError: {err.error_message}\\nFailed Search Block:\\n{err.search_block}\\n"
                if err.suggested_context:
                    prompt += f"\\nContext from file:\\n{err.suggested_context}\\n"
            
            # Request rewrite using the ai_service
            response = self.ai_service.complete(system_prompt="Fix search blocks. Return updated <<<SEARCH/===/>>> blocks.", user_prompt=prompt)
            # Apply corrections
            if response:
                from agent.core.implement.parser import parse_search_replace_blocks
                new_blocks = parse_search_replace_blocks(response)
                # Create a new list to avoid in-place mutation and satisfy QA
                corrected_steps = []
                for step in steps:
                    new_step = step.model_copy()
                    for nb in new_blocks:
                        if new_step.path == nb.get("file"):
                            if nb.get("search"):
                                new_step.search = nb.get("search")
                            if nb.get("replace"):
                                new_step.replace = nb.get("replace")
                    corrected_steps.append(new_step)
                return corrected_steps
            return None
        except Exception as e:
            logger.error(f"Failed to request rewrite: {e}")
            return None
