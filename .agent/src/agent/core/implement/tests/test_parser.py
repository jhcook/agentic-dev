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

"""Integration tests for parser error handling (INFRA-150).

Verifies that the parser raises ParsingError (not silent debug logging)
when encountering malformed [MODIFY] or [NEW] blocks.
"""

import pytest
from pydantic import ValidationError

from agent.core.implement.models import ParsingError
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap_runbook(step_body: str) -> str:
    """Wrap a step body in a minimal valid runbook structure."""
    return (
        "# STORY-ID: TEST-001\n\n"
        "## Implementation Steps\n\n"
        f"### Step 1: Test step\n\n{step_body}"
    )


# ---------------------------------------------------------------------------
# MODIFY header without SEARCH/REPLACE blocks
# ---------------------------------------------------------------------------

class TestModifyParsingError:
    """Verify ParsingError for [MODIFY] headers with no S/R blocks."""

    def test_modify_without_sr_raises_parsing_error(self):
        """A [MODIFY] header with no <<<SEARCH blocks must raise ParsingError."""
        content = _wrap_runbook(
            "#### [MODIFY] src/main.py\n\n"
            "Some description but no search/replace blocks.\n"
        )
        with pytest.raises(ParsingError, match="no valid SEARCH/REPLACE blocks"):
            _extract_runbook_data(content)

    def test_modify_without_sr_surfaces_in_validate(self):
        """validate_runbook_schema should return a violation string for empty MODIFY."""
        content = _wrap_runbook(
            "#### [MODIFY] src/main.py\n\n"
            "Description only, no <<<SEARCH blocks.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) >= 1
        assert "SEARCH/REPLACE" in violations[0]

    def test_modify_with_valid_sr_passes(self):
        """A well-formed [MODIFY] block should extract without errors."""
        content = _wrap_runbook(
            "#### [MODIFY] src/main.py\n\n"
            "```\n"
            "<<<SEARCH\n"
            "old_code()\n"
            "===\n"
            "new_code()\n"
            ">>>\n"
            "```\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        assert steps[0]["operations"][0]["path"] == "src/main.py"


# ---------------------------------------------------------------------------
# NEW header without code fence
# ---------------------------------------------------------------------------

class TestNewParsingError:
    """Verify ParsingError for [NEW] headers with no code block."""

    def test_new_without_code_fence_raises_parsing_error(self):
        """A [NEW] header with no code fence must raise ParsingError."""
        content = _wrap_runbook(
            "#### [NEW] src/new_file.py\n\n"
            "This is just text, no code fence.\n"
        )
        with pytest.raises(ParsingError, match="no (balanced code fence|code block)"):
            _extract_runbook_data(content)

    def test_new_without_fence_surfaces_in_validate(self):
        """validate_runbook_schema should return a violation string for fenceless NEW."""
        content = _wrap_runbook(
            "#### [NEW] src/new_file.py\n\n"
            "Just text, no fenced code block.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) >= 1
        assert "code fence" in violations[0] or "code block" in violations[0]

    def test_new_with_valid_fence_passes(self):
        """A well-formed [NEW] block should extract without errors."""
        content = _wrap_runbook(
            "#### [NEW] src/new_file.py\n\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        assert steps[0]["operations"][0]["path"] == "src/new_file.py"
        assert "print('hello')" in steps[0]["operations"][0]["content"]


# ---------------------------------------------------------------------------
# Missing Implementation Steps section
# ---------------------------------------------------------------------------

class TestMissingImplementationSteps:
    """Verify error handling when the runbook is structurally invalid."""

    def test_missing_impl_section_raises(self):
        """A runbook without '## Implementation Steps' must raise ValueError."""
        content = "# STORY-ID: TEST-001\n\n## Some Other Section\n\nNo steps here.\n"
        with pytest.raises(ValueError, match="Missing.*Implementation Steps"):
            _extract_runbook_data(content)

    def test_missing_impl_section_in_validate(self):
        """validate_runbook_schema should surface the missing section as a violation."""
        content = "# STORY-ID: TEST-001\n\n## Not Implementation\n\nNo steps.\n"
        violations = validate_runbook_schema(content)
        assert any("Implementation Steps" in v for v in violations)


# ---------------------------------------------------------------------------
# DeleteBlock rationale validation through parser pipeline
# ---------------------------------------------------------------------------

class TestDeleteBlockPipeline:
    """Verify DeleteBlock rationale validation through the full pipeline."""

    def test_delete_with_short_rationale_fails_validation(self):
        """A [DELETE] block with a too-short rationale must produce a violation."""
        content = _wrap_runbook(
            "#### [DELETE] old_file.py\n\n"
            "rm\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) >= 1
        assert any("5 characters" in v or "min_length" in v.lower() for v in violations)

    def test_delete_with_valid_rationale_passes(self):
        """A [DELETE] block with a meaningful rationale should pass validation."""
        content = _wrap_runbook(
            "#### [DELETE] old_file.py\n\n"
            "This module is deprecated and replaced by new_file.py.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) == 0
