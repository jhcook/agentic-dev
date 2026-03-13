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
tracer = get_tracer()

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
        Uses fuzzy sequence matching to find the most likely intended location 
        and returns surrounding lines.

        :param file_content: Full content of the file.
        :param search_block: The block that failed to match.
        :return: A snippet of the file content.
        """
        import difflib
        
        file_lines = file_content.splitlines()
        search_lines = search_block.splitlines()
        
        if not file_lines or not search_lines:
            return ""
            
        # If file is small, just return it entirely
        if len(file_lines) <= 200:
            return file_content
            
        # Find the best contiguous match for the search block
        matcher = difflib.SequenceMatcher(None, file_lines, search_lines)
        match = matcher.find_longest_match(0, len(file_lines), 0, len(search_lines))
        
        # Give context of 30 lines above and 30 lines below the best match
        start_idx = max(0, match.a - 30)
        end_idx = min(len(file_lines), match.a + match.size + 30)
        
        return "\n".join(file_lines[start_idx:end_idx])
