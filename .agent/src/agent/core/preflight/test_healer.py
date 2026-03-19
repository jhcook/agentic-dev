# Copyright 2024-2026 Justin Cook
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
Autonomous test failure healer.

Reads pytest tracebacks, identifies the failing source file, asks the AI
for a surgical fix, writes it back, and re-runs the targeted test command.
Changes are staged (not committed) so the developer retains full control.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Optional

from opentelemetry import trace

from agent.core.ai.service import ai_service
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Regex to extract repo-relative source paths from pytest tracebacks.
# Matches both:
#   File "agent/core/utils.py", line 45, ...       (double-quoted)
#   .agent/src/agent/core/utils.py:45: AssertionError
_FILE_RE = re.compile(
    r'(?:File ["\'])([^"\']+\.py)["\']'
    r'|'
    r'(\.agent/src/[^\s:]+\.py):\d+:',
)

# Files that TestHealer must NEVER overwrite — prevents self-modification.
_PROTECTED_RE = re.compile(
    r"agent/core/preflight/(healer|test_healer)\.py$"
    r"|commands/tests/test_preflight_autoheal\.py$"
)


class TestHealer:  # noqa: N801 — name intentional; not a pytest collection target
    """Handles autonomous correction of unit test failures.

    Workflow per attempt:
    1. Extract the failing source file(s) from the pytest traceback.
    2. Read current file content from disk.
    3. Send scrubbed traceback + file content to the AI for a surgical fix.
    4. Write the fixed content back and stage it (``git add``).
    5. Re-run the exact failing test command.
    6. Return True if tests pass, False otherwise.

    The budget is shared across ALL heal_failure() calls on this instance.
    """

    def __init__(self, budget: int = 3) -> None:
        self.budget = budget
        self._attempts = 0

    @tracer.start_as_current_span("heal_test_failure")
    def heal_failure(self, traceback: str, cmd: List[str], cwd: Optional[str] = None) -> bool:
        """Analyse a pytest traceback and attempt a fix.

        Args:
            traceback: The raw pytest stdout+stderr combined output.
            cmd: The exact pytest command that failed (re-run after fix).
            cwd: Working directory for the test command.

        Returns:
            True if the fix was applied and the tests now pass.
        """
        if self._attempts >= self.budget:
            logger.warning("test_healer_budget_exhausted", extra={"budget": self.budget})
            return False

        self._attempts += 1
        scrubbed_tb = scrub_sensitive_data(traceback)
        failing_files = self._extract_failing_files(scrubbed_tb)

        if not failing_files:
            logger.warning("test_healer_no_file", extra={"traceback_snippet": scrubbed_tb[:300]})
            return False

        logger.info("test_healer_attempt", extra={"attempt": self._attempts, "files": failing_files})

        for file_path in failing_files:
            resolved = Path(file_path)
            if not resolved.exists():
                for prefix in ("", ".agent/src/"):
                    candidate = Path(prefix + file_path)
                    if candidate.exists():
                        resolved = candidate
                        break

            if not resolved.exists():
                logger.warning("test_healer_file_not_found", extra={"file": file_path})
                continue

            original_content = resolved.read_text()
            fix_prompt = (
                f"The following pytest failure occurred in `{resolved}`:\n\n"
                f"```\n{scrubbed_tb[:4000]}\n```\n\n"
                f"Current file content:\n```python\n{original_content[:6000]}\n```\n\n"
                "Provide a MINIMAL surgical fix. "
                "Return ONLY the full corrected file content inside a ```python ... ``` fence. "
                "Do not add explanation or prose outside the fence."
            )

            response = ai_service.complete(
                system_prompt=(
                    "You are a senior Python engineer fixing a failing pytest test. "
                    "Return only the corrected file, no prose."
                ),
                user_prompt=fix_prompt,
            )

            if not response:
                logger.warning("test_healer_empty_response", extra={"file": str(resolved)})
                continue

            fixed_content = self._extract_code_fence(response)
            if not fixed_content:
                logger.warning("test_healer_no_fence", extra={"file": str(resolved)})
                continue

            resolved.write_text(fixed_content)
            subprocess.run(["git", "add", str(resolved)], capture_output=True)
            logger.info("test_healer_fix_applied", extra={"file": str(resolved)})

        # Re-run the failing test command
        with tracer.start_as_current_span("test_healer_rerun"):
            res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            passed = res.returncode == 0
            logger.info(
                "test_healer_rerun_result",
                extra={"passed": passed, "attempt": self._attempts},
            )
            return passed

    def _extract_failing_files(self, traceback: str) -> List[str]:
        """Return unique source file paths from a pytest traceback.

        Skips test files and protected healer files to prevent self-modification.
        """
        matches = _FILE_RE.findall(traceback)
        seen: List[str] = []
        for quoted, bare in matches:
            path = quoted or bare
            if not path:
                continue
            if "test_" in Path(path).name:
                continue  # fix source, not test expectations
            if _PROTECTED_RE.search(path):
                continue  # never self-modify
            if path not in seen:
                seen.append(path)
        return seen

    @staticmethod
    def _extract_code_fence(response: str) -> Optional[str]:
        """Extract content from the first ```python ... ``` fence."""
        match = re.search(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
        return match.group(1).strip() if match else None
