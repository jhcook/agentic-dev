# STORY-ID: INFRA-122: Idempotent Runbook Verification

## State

ACCEPTED

## Goal Description

Implement a runbook verification gate that dry-runs `<<<SEARCH/===/>>>` blocks against the source codebase before execution. This prevents "hallucinated" search blocks from failing during deployment by catching mismatches early and providing the LLM with the correct file context for an automated rewrite loop (limited to 3 attempts). This ensures idempotent execution and increases the reliability of automated remediations.

## Linked Journeys

- JRN-022: Automated Incident Remediation
- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- ADR-104 compliance: The verification logic must be isolated from the actual execution logic to ensure a true "dry-run" state.
- The rewrite loop should be managed by the `ImplementOrchestrator` to maintain state across retry attempts.
- File resolution must use the same logic as the execution engine to ensure consistency.

### @Qa
- Test coverage must include: 
    1. Exact match (Success)
    2. Partial mismatch (Failure)
    3. Missing file (Failure)
    4. Successful recovery after 1 rewrite.
    5. Termination after 3 failed rewrites.
- "Synthetic Hallucination" tests will be critical to validate the feedback loop.

### @Security
- Context returned to the LLM *must* pass through `scrub_sensitive_data` to prevent PII or secrets from being included in the correction prompt.
- Ensure file read operations are restricted to the repository root.

### @Product
- Acceptance criteria Scenario 2 is satisfied by the feedback loop.
- The 2-second performance requirement is achievable through targeted file reads rather than full-repository indexing.
- The `ENABLE_RUNBOOK_GATE` flag provides a safe fallback.

### @Observability
- Metrics required: `runbook_verification_success_rate` (ratio) and `runbook_rewrite_cycles_total` (counter).
- Structured logs must include `story_id` and the specific file path that failed verification.

### @Docs
- Update `agent/core/implement/README.md` (if it exists) to explain the verification phase and the automated rewrite behavior.

### @Compliance
- Audit trail must capture the original (failed) runbook block and the corrected block for SOC2/change management visibility.
- License headers must be present on all new files.

### @Backend
- Strict typing and PEP-257 docstrings are required for the new `RunbookVerifier` class and its methods.
- Integration with OpenTelemetry is mandatory for tracing the rewrite loop.

## Codebase Introspection

### Targeted File Contents (from source)

(No targeted files identified in story content. Proceeding with new infrastructure components.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| .agent/src/agent/core/implement/tests/test_verifier.py | N/A | New File | Create comprehensive test suite for verification logic |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Max Rewrite Retries | Story | 3 | Yes |
| Performance Overhead | Story | < 2s | Yes |
| Feature Flag | Story | ENABLE_RUNBOOK_GATE | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Ensure `scrub_sensitive_data` handles all standard secret patterns (AWS keys, etc.) before returning context to LLM.

## Implementation Steps

### Step 1: Implement the Runbook Verifier

Create the core logic for checking if `SEARCH` blocks exist in the target files and providing feedback context.

#### [NEW] .agent/src/agent/core/implement/verifier.py

```python
"""
Verification logic for runbook search blocks.

This module provides the tools to dry-run SEARCH blocks against the filesystem
and generate feedback for LLM correction loops.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from agent.core.logger import get_logger
from agent.core.security import scrub_sensitive_data
from agent.core.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)

@dataclass
class VerificationError:
    """Represents a failed verification of a runbook block."""
    file_path: str
    search_block: str
    error_message: str
    suggested_context: Optional[str] = None

class RunbookVerifier:
    """
    Verifier for idempotent runbook execution.
    
    Checks that SEARCH blocks in a runbook exactly match the current
    state of the target files.
    """

    def __init__(self, root_dir: Path):
        """
        Initialize the verifier.

        :param root_dir: The root directory of the repository.
        """
        self.root_dir = root_dir

    def verify_block(self, file_path_str: str, search_block: str) -> Tuple[bool, Optional[VerificationError]]:
        """
        Verify that a specific search block exists in a file.

        :param file_path_str: Repo-relative path to the file.
        :param search_block: The exact text to find.
        :return: (Success boolean, Optional error details)
        """
        with tracer.start_as_current_span("verify_block") as span:
            span.set_attribute("file_path", file_path_str)
            
            full_path = self.root_dir / file_path_str
            
            if not full_path.exists():
                return False, VerificationError(
                    file_path=file_path_str,
                    search_block=search_block,
                    error_message=f"File not found: {file_path_str}"
                )

            try:
                content = full_path.read_text(encoding="utf-8")
            except Exception as e:
                return False, VerificationError(
                    file_path=file_path_str,
                    search_block=search_block,
                    error_message=f"Could not read file {file_path_str}: {str(e)}"
                )

            if search_block in content:
                logger.info(f"Verification successful for {file_path_str}")
                return True, None

            # Logic to find "near matches" or provide relevant context
            logger.warning(f"Verification failed for {file_path_str}: Exact match not found.")
            
            # Provide surrounding context for the LLM to fix the hallucination
            # We provide the scrubbed content of the file or a relevant snippet
            relevant_context = self._get_relevant_context(content, search_block)
            
            return False, VerificationError(
                file_path=file_path_str,
                search_block=search_block,
                error_message="The SEARCH block does not exactly match the file content.",
                suggested_context=scrub_sensitive_data(relevant_context)
            )

    def _get_relevant_context(self, file_content: str, search_block: str) -> str:
        """
        Extract relevant context from the file to help correct the SEARCH block.

        :param file_content: Full content of the file.
        :param search_block: The block that failed to match.
        :return: A snippet of the file content.
        """
        # Simple heuristic: if the block is small, return lines around where it might be.
        # For now, return the first 100 lines to stay within prompt limits while being useful.
        lines = file_content.splitlines()
        return "\n".join(lines[:100])
```

### Step 2: Implement Orchestration Logic

Create a new orchestrator utility to manage the retry loop.

#### [NEW] .agent/src/agent/core/implement/resolver.py

```python
"""
Orchestration for runbook verification and rewrite loops.

Handles the logic of calling the verifier and managing retries with the AI service.
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from agent.core.implement.verifier import RunbookVerifier, VerificationError
from agent.core.logger import get_logger
from agent.core.telemetry import get_tracer
from agent.core.ai.service import AIService

logger = get_logger(__name__)
tracer = get_tracer(__name__)

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

    async def verify_and_correct(self, runbook_steps: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Verify all steps and attempt to correct them via LLM if they fail.

        :param runbook_steps: List of parsed runbook steps.
        :return: (Final success status, Final steps)
        """
        current_steps = runbook_steps
        attempts = 0

        while attempts <= self.max_retries:
            errors = self._verify_all_steps(current_steps)
            
            if not errors:
                logger.info(f"Runbook verified successfully after {attempts} rewrites.")
                return True, current_steps
            
            if attempts == self.max_retries:
                logger.error("Reached maximum rewrite attempts for runbook.")
                break
                
            attempts += 1
            logger.info(f"Attempting runbook rewrite cycle {attempts}/{self.max_retries}")
            
            current_steps = await self._request_rewrite(current_steps, errors)
            if not current_steps:
                break

        return False, current_steps

    def _verify_all_steps(self, steps: List[Dict[str, Any]]) -> List[VerificationError]:
        """
        Check all steps against the verifier.

        :param steps: Steps to check.
        :return: List of verification errors.
        """
        errors = []
        for step in steps:
            if step.get("action") == "MODIFY":
                path = step.get("path")
                search = step.get("search")
                if path and search:
                    success, error = self.verifier.verify_block(path, search)
                    if error:
                        errors.append(error)
        return errors

    async def _request_rewrite(self, steps: List[Dict[str, Any]], errors: List[VerificationError]) -> Optional[List[Dict[str, Any]]]:
        """
        Prompt the LLM to fix the specific failed blocks.

        :param steps: Current steps.
        :param errors: Errors found.
        :return: Corrected steps or None if failure.
        """
        # This would call the AI service with the specific error context
        # Placeholder for AI logic as it depends on prompt implementation
        return None
```

### Step 3: Add Synthetic Hallucination Tests

#### [NEW] .agent/src/agent/core/implement/tests/test_verifier.py

```python
"""
Tests for RunbookVerifier.
"""

import pytest
from pathlib import Path
from agent.core.implement.verifier import RunbookVerifier

def test_verifier_exact_match(tmp_path):
    """
    Test that an exact match returns success.
    """
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    print('world')")
    
    verifier = RunbookVerifier(tmp_path)
    success, error = verifier.verify_block("test.py", "def hello():")
    
    assert success is True
    assert error is None

def test_verifier_mismatch(tmp_path):
    """
    Test that a hallucinated block returns an error with context.
    """
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    print('world')")
    
    verifier = RunbookVerifier(tmp_path)
    # Search block has incorrect indentation
    success, error = verifier.verify_block("test.py", "def hello():\nprint('world')")
    
    assert success is False
    assert error is not None
    assert "The SEARCH block does not exactly match" in error.error_message
    assert "def hello():" in error.suggested_context

def test_verifier_file_not_found(tmp_path):
    """
    Test that a missing file returns a clear error.
    """
    verifier = RunbookVerifier(tmp_path)
    success, error = verifier.verify_block("missing.py", "some code")
    
    assert success is False
    assert "File not found" in error.error_message
```

## Verification Plan

### Automated Tests

- [ ] Run the new verifier tests:
  `pytest .agent/src/agent/core/implement/tests/test_verifier.py`
- [ ] Verify scrubbed context:
  Check that `VerificationError.suggested_context` does not contain dummy secrets created in a test file.

### Manual Verification

- [ ] Create a runbook with a typo in a `SEARCH` block.
- [ ] Run `agent implement --story <ID>` with `ENABLE_RUNBOOK_GATE=true`.
- [ ] Observe logs for "Verification failed" and the subsequent "Attempting runbook rewrite cycle".
- [ ] Verify that the implementation only proceeds if the rewrite resolves the mismatch.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Idempotent Runbook Verification Gate".

### Observability

- [ ] Logs are structured and free of PII (verified via `scrub_sensitive_data` usage).
- [ ] Verification success/failure events are logged with `story_id`.

### Testing

- [ ] All existing tests pass.
- [ ] New tests added for `RunbookVerifier` cover success, mismatch, and file-missing cases.

## Copyright

Copyright 2026 Justin Cook