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

"""Tests for sr_validation.py — INFRA-159 dedent-normalised match layer.

Covers:
  - _dedent_normalize_match: successful match when AI drops class-level indent
  - _dedent_normalize_match: returns None when content genuinely absent
  - validate_and_correct_sr_blocks: indentation error corrected without AI call
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.implement.sr_validation import (
    _dedent_normalize_match,
    validate_and_correct_sr_blocks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Simulates a file where a method lives inside a class (4-space class indent)
_FILE_WITH_CLASS = """\
class MyService:
    def process(self, data):
        \"\"\"Process data.\"\"\"
        return data.strip()

    def validate(self, value):
        \"\"\"Validate a value.\"\"\"
        if not value:
            raise ValueError("empty")
        return True
"""

# The AI hallucinated the method without class-level indentation
_SEARCH_MISSING_INDENT = """\
def process(self, data):
    \"\"\"Process data.\"\"\"
    return data.strip()"""

# Correctly-indented version — what _dedent_normalize_match should return
_SEARCH_CORRECT_INDENT = """\
    def process(self, data):
        \"\"\"Process data.\"\"\"
        return data.strip()"""

# Content that is genuinely not present even when stripped
_SEARCH_COMPLETELY_WRONG = """\
def nonexistent_method(self):
    return 42"""


# ---------------------------------------------------------------------------
# Unit tests: _dedent_normalize_match
# ---------------------------------------------------------------------------


class TestDedentNormalizeMatch:
    """Unit tests for the Layer 1.5 dedent-normalised matching helper."""

    def test_successful_match_returns_correctly_indented_text(self):
        """AI drops class-level 4-space indent; function recovers the real text.

        The SEARCH block is identical in content but stripped of the leading
        class indentation.  _dedent_normalize_match should find the correctly
        indented region in the file and return it verbatim.
        """
        result = _dedent_normalize_match(_SEARCH_MISSING_INDENT, _FILE_WITH_CLASS)

        assert result is not None, (
            "_dedent_normalize_match returned None for a valid indentation-shift mismatch"
        )
        assert result == _SEARCH_CORRECT_INDENT, (
            f"Expected correctly-indented text, got:\n{result!r}"
        )

    def test_no_match_returns_none_for_absent_content(self):
        """Content that doesn't exist even after stripping → returns None.

        Verifies that the function does not produce false-positive matches
        when the SEARCH block has genuinely wrong content.
        """
        result = _dedent_normalize_match(_SEARCH_COMPLETELY_WRONG, _FILE_WITH_CLASS)

        assert result is None, (
            f"Expected None for genuinely absent content, got:\n{result!r}"
        )

    def test_no_match_on_empty_search(self):
        """Empty or whitespace-only search text returns None (guard clause)."""
        assert _dedent_normalize_match("", _FILE_WITH_CLASS) is None
        assert _dedent_normalize_match("   \n   ", _FILE_WITH_CLASS) is None

    def test_exact_match_also_works_via_dedent(self):
        """An already-correct SEARCH block also passes through the dedent path."""
        result = _dedent_normalize_match(_SEARCH_CORRECT_INDENT, _FILE_WITH_CLASS)
        # Either the exact text OR None is acceptable — exact match exits before
        # reaching _dedent_normalize_match in the real pipeline, but the helper
        # itself must not crash on correctly-indented input.
        if result is not None:
            assert result == _SEARCH_CORRECT_INDENT


# ---------------------------------------------------------------------------
# Integration test: validate_and_correct_sr_blocks — no AI call path
# ---------------------------------------------------------------------------


class TestValidateAndCorrectSrBlocksNoAiCall:
    """Integration tests for the dedent-correction layer inside validate_and_correct_sr_blocks."""

    def _make_runbook(self, filepath: str, search_text: str, replace_text: str) -> str:
        """Build a minimal runbook string with one [MODIFY] S/R block."""
        return (
            f"#### [MODIFY] `{filepath}`\n"
            f"<<<SEARCH\n{search_text}\n===\n{replace_text}\n>>>"
        )

    def test_indentation_error_corrected_without_ai_call(self, tmp_path: Path):
        """Indentation-shifted SEARCH block is corrected by Layer 1.5.

        Given a runbook whose SEARCH block has the class-level indentation
        stripped (the canonical AI hallucination), validate_and_correct_sr_blocks
        should fix it using _dedent_normalize_match and never reach the AI
        re-anchor path.
        """
        # Write the target file to disk inside tmp_path
        target = tmp_path / "service.py"
        target.write_text(_FILE_WITH_CLASS)

        replace_text = "    def process(self, data):\n        return data.strip().upper()"
        runbook = self._make_runbook("service.py", _SEARCH_MISSING_INDENT, replace_text)

        # Patch _ai_reanchor_search to assert it is NEVER called
        with patch(
            "agent.core.implement.sr_validation._ai_reanchor_search"
        ) as mock_ai:
            corrected, total, count = validate_and_correct_sr_blocks(
                runbook, repo_root=tmp_path
            )

        # The block must have been corrected
        assert count == 1, f"Expected 1 corrected block, got {count}"
        assert total == 1, f"Expected 1 total block, got {total}"

        # The corrected runbook must contain the properly-indented SEARCH
        assert _SEARCH_CORRECT_INDENT in corrected, (
            "Corrected runbook does not contain the properly-indented SEARCH anchor"
        )
        # The wrong (stripped) version must no longer appear
        assert _SEARCH_MISSING_INDENT not in corrected, (
            "Corrected runbook still contains the stripped (wrong) SEARCH anchor"
        )

        # AI re-anchor must NOT have been called — this was a zero-AI correction
        mock_ai.assert_not_called()

    def test_exact_match_blocks_not_counted_as_corrected(self, tmp_path: Path):
        """A perfectly-correct SEARCH block is accepted as-is with corrected_count=0."""
        target = tmp_path / "service.py"
        target.write_text(_FILE_WITH_CLASS)

        replace_text = "    def process(self, data):\n        return data.strip().upper()"
        runbook = self._make_runbook("service.py", _SEARCH_CORRECT_INDENT, replace_text)

        corrected, total, count = validate_and_correct_sr_blocks(
            runbook, repo_root=tmp_path
        )

        assert total == 1
        assert count == 0, "Exact match must not increment corrected_count"
