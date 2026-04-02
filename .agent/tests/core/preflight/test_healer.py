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
TestHealer: autonomous fixer for pytest failures (INFRA-163).

Parses a pytest traceback to identify the *source* files responsible for
failures, then asks the AI to produce surgical edits in [MODIFY] block
format, writes those edits to disk, and stages them.  Test files and
protected healer files are never targeted.
"""

import re
from pathlib import Path
from typing import List, Optional

from agent.core.ai.service import ai_service
from agent.core.logger import get_logger
from agent.core.preflight.healer import _PATH_CONTENT_RE, _PROTECTED_RE
from agent.core.utils import scrub_sensitive_data

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Extracts file paths from Python tracebacks in two forms:
#   1. Quoted:   File "some/path.py", line N
#   2. Bare:     .agent/src/some/path.py:N:
#
# Returns 2-tuples (quoted_path, bare_path); exactly one will be non-empty.
_FILE_RE = re.compile(
    r'File "([^"]+\.py)"'         # group 1: quoted path (inside traceback frames)
    r"|"
    r"((?:\.agent/src/|\./)?[a-zA-Z0-9_./]+\.py):\d+"  # group 2: bare colon-separated path
)


class TestHealer:
    """Autonomous correction of pytest failures.

    Workflow per ``heal_failure()`` call:
    1. Parse the traceback for *source* files (not test files, not protected).
    2. Scrub PII from the traceback before forwarding to AI.
    3. Ask the AI for ``[MODIFY]`` blocks targeting those files.
    4. Write each fix and stage with ``git add``.

    The budget is shared across all ``heal_failure()`` calls on this instance.
    """

    def __init__(self, budget: int = 3) -> None:
        self.budget = budget
        self._attempts = 0

    def heal_failure(
        self,
        traceback: str,
        cmd: List[str],
        extra: Optional[object],
    ) -> bool:
        """Attempt to fix failing tests by patching source files.

        Args:
            traceback: Full pytest output / traceback text.
            cmd: The pytest command that was run (used for context).
            extra: Reserved for future use; currently unused.

        Returns:
            True if at least one file edit was successfully applied.
        """
        if self._attempts >= self.budget:
            logger.warning(
                "test_healer_budget_exhausted",
                extra={"budget": self.budget},
            )
            return False

        self._attempts += 1

        failing_files = self._extract_failing_files(traceback)
        scrubbed_tb = scrub_sensitive_data(traceback)

        prompt = (
            "## Pytest Failure — TestHealer\n\n"
            f"**Failing source files:** {', '.join(failing_files) or 'unknown'}\n\n"
            f"**Traceback (scrubbed):**\n```\n{scrubbed_tb[:4000]}\n```\n\n"
            "Apply the minimum surgical changes to fix every failing test above.\n"
            "For each file that needs editing, output a block in this exact format:\n\n"
            "#### [MODIFY] path/to/file.py\n"
            "```python\n"
            "<full corrected file content>\n"
            "```\n\n"
            "Return ONLY these blocks — no prose, no explanation."
        )

        logger.info(
            "test_healer_attempt",
            extra={"attempt": self._attempts, "files": failing_files},
        )

        response = ai_service.complete(
            system_prompt=(
                "You are a senior engineer applying targeted fixes to make "
                "failing Python tests pass. Output only [MODIFY] blocks."
            ),
            user_prompt=prompt,
        )

        if not response:
            logger.warning("test_healer_empty_response")
            return False

        edits = _PATH_CONTENT_RE.findall(response)
        if not edits:
            logger.warning(
                "test_healer_no_edits_parsed",
                extra={"response_snippet": response[:300]},
            )
            return False

        applied = self._apply_staged_changes(edits)
        logger.info("test_healer_applied", extra={"files": applied})
        return bool(applied)

    def _extract_failing_files(self, traceback: str) -> List[str]:
        """Extract unique *source* file paths from a pytest traceback.

        Excludes:
        - Test files (filename starts with ``test_``).
        - Files matching ``_PROTECTED_RE`` (healer and sibling files).

        Args:
            traceback: Raw pytest output text.

        Returns:
            Deduplicated list of candidate source file paths.
        """
        seen: List[str] = []
        for quoted, bare in _FILE_RE.findall(traceback):
            path = quoted or bare
            if not path:
                continue
            filename = Path(path).name
            if filename.startswith("test_"):
                continue
            if _PROTECTED_RE.search(path):
                continue
            if path not in seen:
                seen.append(path)
        return seen

    def _apply_staged_changes(self, edits: List[tuple]) -> List[str]:
        """Write each (path, content) pair to disk and stage with git add.

        Protected files are silently skipped.

        Args:
            edits: List of (repo_relative_path, file_content) tuples from
                   ``_PATH_CONTENT_RE``.

        Returns:
            List of file paths successfully written and staged.
        """
        import subprocess  # local import keeps module lightweight

        applied: List[str] = []
        for raw_path, content in edits:
            path = raw_path.strip()
            if _PROTECTED_RE.search(path):
                logger.warning(
                    "test_healer_protected_skip", extra={"file": path}
                )
                continue
            resolved = Path(path)
            if not resolved.parent.exists():
                resolved.parent.mkdir(parents=True, exist_ok=True)
            try:
                resolved.write_text(content.strip() + "\n")
                subprocess.run(
                    ["git", "add", str(resolved)],
                    capture_output=True,
                    check=True,
                )
                applied.append(path)
                logger.info("test_healer_file_written", extra={"file": path})
            except Exception as exc:
                logger.error(
                    "test_healer_write_failed",
                    extra={"file": path, "error": str(exc)},
                )
        return applied
