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

Verifies that the parser flags malformed [MODIFY] or [NEW] blocks
with malformed=True so downstream consumers can handle them as
correctable gate findings instead of crashing.
"""

import pytest
from pydantic import ValidationError

from agent.core.implement.models import ParsingError
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
    parse_skeleton,
)    InvalidTemplateError,
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
    """Verify malformed flag for [MODIFY] headers with no S/R blocks."""

    def test_modify_without_sr_flags_malformed(self):
        """A [MODIFY] header with no <<<SEARCH blocks must be flagged malformed."""
        content = _wrap_runbook(
            "#### [MODIFY] src/main.py\n\n"
            "Some description but no search/replace blocks.\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op["path"] == "src/main.py"
        assert op.get("malformed") is True

    def test_modify_without_sr_surfaces_in_validate(self):
        """validate_runbook_schema should return a violation for empty MODIFY."""
        content = _wrap_runbook(
            "#### [MODIFY] src/main.py\n\n"
            "Description only, no <<<SEARCH blocks.\n"
        )
        violations = validate_runbook_schema(content)
        # Malformed blocks may surface as Pydantic validation errors (empty blocks list)
        # or as structural warnings — either way, at least one violation expected.
        assert len(violations) >= 1

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
    """Verify malformed flag for [NEW] headers with no code block."""

    def test_new_without_code_fence_flags_malformed(self):
        """A [NEW] header with no code fence must be flagged malformed."""
        content = _wrap_runbook(
            "#### [NEW] src/new_file.py\n\n"
            "This is just text, no code fence.\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op["path"] == "src/new_file.py"
        assert op.get("malformed") is True

    def test_new_without_fence_surfaces_in_validate(self):
        """validate_runbook_schema should return a violation for fenceless NEW."""
        content = _wrap_runbook(
            "#### [NEW] src/new_file.py\n\n"
            "Just text, no fenced code block.\n"
        )
        violations = validate_runbook_schema(content)
        # Malformed blocks surface as Pydantic validation errors (empty content)
        # or structural warnings.
        assert len(violations) >= 1

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

class TestSecurityValidation:
    """Verify security constraints for paths and identifiers."""

    def test_traversal_detection_in_path(self):
        """Ensure that paths with .. or absolute roots are blocked."""
        with pytest.raises(ParsingError, match="Security Violation"):
            validate_runbook_schema(_wrap_runbook("#### [NEW] ../../etc/passwd\n\n```\ncode\n```"))

    def test_absolute_path_detection(self):
        """Ensure absolute paths are blocked for runbook operations."""
        with pytest.raises(ParsingError, match="Security Violation"):
            validate_runbook_schema(_wrap_runbook("#### [MODIFY] /var/log/syslog\n\n<<<SEARCH\nx\n===\ny\n>>>"))


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


class TestSkeletonParser:
    """Unit tests for regex logic and block mapping (INFRA-168)."""

    def test_regex_block_identification(self):
        """Verify that block boundaries are correctly identified by the parser."""
        content = "<!-- @block id1 -->content1<!-- @end -->"
        skeleton = parse_skeleton(content)
        assert len(skeleton.blocks) == 1
        assert skeleton.blocks[0].id == "id1"
        assert skeleton.blocks[0].content == "content1"

    def test_block_metadata_mapping(self):
        """Verify extraction of metadata tokens from block tags."""
        content = "<!-- @block id1 version=2.0 tags=infra,test -->content<!-- @end -->"
        skeleton = parse_skeleton(content)
        meta = skeleton.blocks[0].metadata
        assert meta.get("version") == "2.0"
        assert "infra" in meta.get("tags", "")

class TestSkeletonParser:
    """Verify decomposition of templates into addressable blocks (INFRA-168)."""

    def test_parse_skeleton_success(self):
        """Verify valid blocks are extracted with metadata and whitespace preservation."""
        template = (
            "# Document Prelude\n"
            "  <!-- block: section-1 category=intro -->\n"
            "  Initial content\n"
            "  <!-- /block -->\n"
            "\n"
            "<!-- block: section-2 version=2.0 -->\n"
            "Secondary content\n"
            "<!-- /block -->\n"
            "EOF footer"
        )
        skeleton = parse_skeleton(template)
        assert len(skeleton.blocks) == 2
        
        b1 = skeleton.get_block("section-1")
        assert b1.metadata["category"] == "intro"
        assert "Initial content" in b1.content
        assert b1.prefix_whitespace == "# Document Prelude\n  "
        
        b2 = skeleton.get_block("section-2")
        assert b2.metadata["version"] == "2.0"
        assert b2.suffix_whitespace == "\nEOF footer"

    def test_parse_skeleton_duplicate_id_raises(self):
        """Verify duplicate block IDs trigger InvalidTemplateError."""
        template = (
            "<!-- block: same --> content <!-- /block -->\n"
            "<!-- block: same --> content <!-- /block -->"
        )
        with pytest.raises(InvalidTemplateError, match="Duplicate block ID"):
            parse_skeleton(template)

    def test_parse_skeleton_no_blocks_raises(self):
        """Verify templates without block markers trigger InvalidTemplateError."""
        template = "Plain text without any addressable blocks."
        with pytest.raises(InvalidTemplateError, match="No addressable blocks"):
            parse_skeleton(template)
