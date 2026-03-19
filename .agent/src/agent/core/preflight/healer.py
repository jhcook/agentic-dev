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
Autonomous governance healer for preflight violations.

Extracts REQUIRED_CHANGES from a blocked governance role verdict, asks the
AI for surgical file edits, applies them, and stages the changes for review.
The caller governs retry budget.
"""

import re
import subprocess
from pathlib import Path
from typing import List

from opentelemetry import trace

from agent.core.ai.service import ai_service
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Matches runbook-style MODIFY blocks so we can reuse the same parser
# the implement command uses.  Falls back to a simple code-fence extractor.
_PATH_CONTENT_RE = re.compile(
    r"####\s*\[MODIFY\]\s*([^\n]+)\n```(?:[a-z]*)?\s*\n(.*?)```",
    re.DOTALL,
)

# Files that the healer must NEVER overwrite — prevents self-modification.
_PROTECTED_RE = re.compile(
    r"agent/core/preflight/(healer|test_healer)\.py$"
    r"|commands/tests/test_preflight_autoheal\.py$"
)


class PreflightHealer:
    """Autonomous correction of governance BLOCK verdicts.

    Workflow per ``heal()`` call:
    1. Build a targeted prompt from ``role``, ``findings``, and
       ``required_changes`` (PII-scrubbed).
    2. Call the AI for surgical edits expressed as standard ``[MODIFY]`` blocks.
    3. Parse the AI response for file paths + new content.
    4. Write each fix to disk and stage it with ``git add``.

    The budget is shared across ALL heal() calls on this instance — create
    once before the governance retry loop, not once per iteration.
    """

    def __init__(self, budget: int = 3) -> None:
        self.budget = budget
        self._attempts = 0

    @tracer.start_as_current_span("heal_governance_violation")
    def heal(
        self,
        role: str,
        findings: str,
        required_changes: "list | str",
        diff: str,
    ) -> bool:
        """Attempt to fix a governance violation for a specific role.

        Args:
            role: The role that issued the BLOCK (e.g. ``Security``).
            findings: The free-text findings from the governance council.
            required_changes: Actionable ``REQUIRED_CHANGES`` from the verdict
                              (list of strings or pre-joined string).
            diff: The current staged git diff (already PII-scrubbed by caller).

        Returns:
            True if at least one file edit was successfully applied.
        """
        if self._attempts >= self.budget:
            logger.warning("governance_healer_budget_exhausted", extra={"role": role, "budget": self.budget})
            return False

        self._attempts += 1

        if isinstance(required_changes, list):
            required_changes = "\n".join(f"- {c}" for c in required_changes)

        prompt = (
            f"## Governance BLOCK — @{role}\n\n"
            f"**Findings:**\n{scrub_sensitive_data(findings)}\n\n"
            f"**Required changes:**\n{scrub_sensitive_data(required_changes)}\n\n"
            f"**Current staged diff:**\n```diff\n{scrub_sensitive_data(diff)[:4000]}\n```\n\n"
            "Apply the minimum surgical changes to resolve every REQUIRED_CHANGES item above.\n"
            "For each file that needs editing, output a block in this exact format:\n\n"
            "#### [MODIFY] path/to/file.py\n"
            "```python\n"
            "<full corrected file content>\n"
            "```\n\n"
            "Return ONLY these blocks — no prose, no explanation."
        )

        logger.info("governance_healer_attempt", extra={"role": role, "attempt": self._attempts})

        response = ai_service.complete(
            system_prompt=(
                "You are a senior engineer applying targeted code fixes to satisfy "
                "governance requirements. Output only [MODIFY] blocks as instructed."
            ),
            user_prompt=prompt,
        )

        if not response:
            logger.warning("governance_healer_empty_response", extra={"role": role})
            return False

        edits = _PATH_CONTENT_RE.findall(response)
        if not edits:
            logger.warning("governance_healer_no_edits_parsed", extra={"role": role, "response_snippet": response[:300]})
            return False

        applied = self._apply_staged_changes(edits)
        logger.info("governance_healer_applied", extra={"role": role, "files": applied})
        return bool(applied)

    def _apply_staged_changes(self, edits: List[tuple]) -> List[str]:
        """Write each (path, content) pair to disk and stage with git add.

        Files matching ``_PROTECTED_RE`` are silently skipped to prevent the
        healer from overwriting its own implementation.

        Args:
            edits: List of (repo_relative_path, file_content) tuples.

        Returns:
            List of file paths that were successfully written and staged.
        """
        applied: List[str] = []
        for raw_path, content in edits:
            path = raw_path.strip()
            if _PROTECTED_RE.search(path):
                logger.warning("governance_healer_protected_skip", extra={"file": path})
                continue
            resolved = Path(path)
            if not resolved.parent.exists():
                resolved.parent.mkdir(parents=True, exist_ok=True)
            try:
                resolved.write_text(content.strip() + "\n")
                subprocess.run(["git", "add", str(resolved)], capture_output=True, check=True)
                applied.append(path)
                logger.info("governance_healer_file_written", extra={"file": path})
            except Exception as exc:
                logger.error("governance_healer_write_failed", extra={"file": path, "error": str(exc)})
        return applied
