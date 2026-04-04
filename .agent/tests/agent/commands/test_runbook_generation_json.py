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

"""Tests for INFRA-181: structured JSON runbook generation and assembly.

Covers:
- RunbookOpJson validation (AC-1, AC-2)
- _sanitize_json_values recursive fence stripping (AC-3)
- _assemble_block_from_json delimiter injection for all op types (AC-4)
- GenerationBlock.from_dict ops-path routing (AC-4)
- Legacy content fallback (AC-5)
- generate_block_prompt schema switching via legacy flag (AC-6)
"""

import pytest

from agent.commands.runbook_generation import (
    GenerationBlock,
    _assemble_block_from_json,
    _sanitize_json_values,
)
from agent.core.ai.prompts import generate_block_prompt
from agent.core.models.runbook import RunbookOpJson


# ---------------------------------------------------------------------------
# RunbookOpJson — Pydantic model validation
# ---------------------------------------------------------------------------

class TestRunbookOpJson:
    """AC-1/AC-2: Schema enforces required fields per op type."""

    def test_new_op_valid(self):
        op = RunbookOpJson(op="new", file="src/foo.py", content="x = 1")
        assert op.op == "new"
        assert op.file == "src/foo.py"
        assert op.content == "x = 1"

    def test_modify_op_valid(self):
        op = RunbookOpJson(op="modify", file="src/bar.py", search="old", replace="new")
        assert op.search == "old"
        assert op.replace == "new"

    def test_delete_op_valid(self):
        op = RunbookOpJson(op="delete", file="src/baz.py", rationale="no longer needed")
        assert op.rationale == "no longer needed"

    def test_modify_missing_search_raises(self):
        with pytest.raises(Exception, match=r"(?i)search|replace|validation"):
            RunbookOpJson(op="modify", file="x.py", replace="new")

    def test_modify_missing_replace_raises(self):
        with pytest.raises(Exception, match=r"(?i)search|replace|validation"):
            RunbookOpJson(op="modify", file="x.py", search="old")

    def test_new_missing_content_raises(self):
        with pytest.raises(Exception, match=r"(?i)content|validation"):
            RunbookOpJson(op="new", file="x.py")

    def test_delete_missing_rationale_raises(self):
        with pytest.raises(Exception, match=r"(?i)rationale|validation"):
            RunbookOpJson(op="delete", file="x.py")

    def test_invalid_op_literal_raises(self):
        with pytest.raises(Exception):
            RunbookOpJson(op="create", file="x.py", content="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _sanitize_json_values — recursive fence stripping
# ---------------------------------------------------------------------------

class TestSanitizeJsonValues:
    """AC-3: Sanitizer strips markdown fences from all string values."""

    def test_strips_python_fence_from_string(self):
        result = _sanitize_json_values("```python\nprint(1)\n```")
        assert "```" not in result
        assert "print(1)" in result

    def test_strips_bare_fence_from_string(self):
        result = _sanitize_json_values("```\nx = 1\n```")
        assert "```" not in result
        assert "x = 1" in result

    def test_strips_tilde_fence(self):
        result = _sanitize_json_values("~~~\ncode\n~~~")
        assert "~~~" not in result
        assert "code" in result

    def test_nested_dict_sanitized(self):
        data = {"op": "new", "content": "```python\ncode\n```"}
        result = _sanitize_json_values(data)
        assert "```" not in result["content"]
        assert "code" in result["content"]

    def test_nested_list_sanitized(self):
        data = [{"content": "```\nline\n```"}, {"search": "```\nold\n```"}]
        result = _sanitize_json_values(data)
        assert "```" not in result[0]["content"]
        assert "```" not in result[1]["search"]

    def test_non_string_values_pass_through(self):
        data = {"count": 3, "flag": True, "nested": {"num": 42}}
        result = _sanitize_json_values(data)
        assert result["count"] == 3
        assert result["flag"] is True
        assert result["nested"]["num"] == 42

    def test_clean_string_unchanged(self):
        code = "def foo():\n    return 1"
        result = _sanitize_json_values(code)
        assert result == code


# ---------------------------------------------------------------------------
# _assemble_block_from_json — delimiter injection
# ---------------------------------------------------------------------------

class TestAssembleBlockFromJson:
    """AC-4: Python injects <<<SEARCH/===/>>> and #### headers; LLM never writes them."""

    def _block(self, ops):
        return GenerationBlock.from_dict({"header": "Test", "ops": ops})

    def test_new_op_injects_header_and_fence(self):
        block = self._block([{"op": "new", "file": "src/mod.py", "content": "x = 1"}])
        result = _assemble_block_from_json(block)
        assert "#### [NEW] src/mod.py" in result
        assert "```python" in result
        assert "x = 1" in result

    def test_modify_op_injects_sr_delimiters(self):
        block = self._block([{
            "op": "modify", "file": "src/app.py",
            "search": "old code", "replace": "new code",
        }])
        result = _assemble_block_from_json(block)
        assert "#### [MODIFY] src/app.py" in result
        assert "<<<SEARCH" in result
        assert "old code" in result
        assert "===" in result
        assert "new code" in result
        assert ">>>" in result

    def test_delete_op_injects_header_and_rationale(self):
        block = self._block([{
            "op": "delete", "file": "src/old.py", "rationale": "deprecated",
        }])
        result = _assemble_block_from_json(block)
        assert "#### [DELETE] src/old.py" in result
        assert "deprecated" in result

    def test_multiple_ops_all_present(self):
        block = self._block([
            {"op": "new", "file": "a.py", "content": "pass"},
            {"op": "modify", "file": "b.py", "search": "x", "replace": "y"},
            {"op": "delete", "file": "c.py", "rationale": "gone"},
        ])
        result = _assemble_block_from_json(block)
        assert "#### [NEW] a.py" in result
        assert "#### [MODIFY] b.py" in result
        assert "#### [DELETE] c.py" in result

    def test_language_inferred_from_extension_yaml(self):
        block = self._block([{"op": "new", "file": "config.yaml", "content": "key: val"}])
        result = _assemble_block_from_json(block)
        assert "```yaml" in result

    def test_language_inferred_from_extension_md(self):
        block = self._block([{"op": "new", "file": "README.md", "content": "# Title"}])
        result = _assemble_block_from_json(block)
        assert "```markdown" in result

    def test_unknown_extension_uses_bare_fence(self):
        block = self._block([{"op": "new", "file": "file.xyz", "content": "data"}])
        result = _assemble_block_from_json(block)
        # bare fence (no language tag after ```)
        assert "```\n" in result or "```" in result

    def test_ops_uppercase_action(self):
        """op field is uppercased in the header regardless of input case."""
        block = self._block([{"op": "MODIFY", "file": "x.py", "search": "a", "replace": "b"}])
        result = _assemble_block_from_json(block)
        assert "#### [MODIFY] x.py" in result


# ---------------------------------------------------------------------------
# GenerationBlock.from_dict — routing logic
# ---------------------------------------------------------------------------

class TestGenerationBlockFromDict:
    """AC-4/AC-5: from_dict routes to ops-path or legacy content-path."""

    def test_ops_path_selected_when_ops_present(self):
        block = GenerationBlock.from_dict({
            "header": "H",
            "ops": [{"op": "new", "file": "f.py", "content": "x=1"}],
        })
        assert block.ops
        assert block.content == ""

    def test_content_path_selected_when_no_ops(self):
        block = GenerationBlock.from_dict({"header": "H", "content": "legacy content"})
        assert block.content == "legacy content"
        assert block.ops == []

    def test_header_fallback_to_title(self):
        block = GenerationBlock.from_dict({"title": "My Title", "content": ""})
        assert block.header == "My Title"

    def test_empty_ops_list_uses_content(self):
        block = GenerationBlock.from_dict({"header": "H", "ops": [], "content": "fallback"})
        assert block.content == "fallback"
        assert block.ops == []

    def test_fences_stripped_from_ops_content_at_from_dict(self):
        """Sanitizer runs inside from_dict on the ops path."""
        block = GenerationBlock.from_dict({
            "header": "H",
            "ops": [{"op": "new", "file": "f.py", "content": "```python\nx=1\n```"}],
        })
        assert "```" not in block.ops[0]["content"]


# ---------------------------------------------------------------------------
# Legacy fallback
# ---------------------------------------------------------------------------

class TestLegacyFallback:
    """AC-5: Blocks with legacy content= return it unchanged via the assembler."""

    def test_assembler_returns_content_when_no_ops(self):
        block = GenerationBlock.from_dict({"header": "H", "content": "#### [NEW] path\n```\ncode\n```"})
        result = _assemble_block_from_json(block)
        assert result == "#### [NEW] path\n```\ncode\n```"

    def test_assembler_returns_empty_string_for_empty_content_and_no_ops(self):
        block = GenerationBlock(header="H", content="", ops=[])
        result = _assemble_block_from_json(block)
        assert result == ""


# ---------------------------------------------------------------------------
# generate_block_prompt — schema switching
# ---------------------------------------------------------------------------

class TestGenerateBlockPromptSchema:
    """AC-6: Prompt includes JSON ops schema by default; legacy flag restores content schema."""

    def _prompt(self, legacy: bool) -> str:
        return generate_block_prompt(
            section_title="Test Section",
            section_desc="A test section.",
            skeleton_json='{"sections": []}',
            story_content="As a user I want something.",
            context_summary="No context.",
            legacy=legacy,
        )

    def test_default_non_legacy_includes_ops_schema(self):
        p = self._prompt(legacy=False)
        assert '"ops"' in p

    def test_default_non_legacy_has_raw_code_rule(self):
        p = self._prompt(legacy=False)
        assert "RAW CODE" in p

    def test_default_non_legacy_mentions_pipeline_injects_delimiters(self):
        p = self._prompt(legacy=False)
        assert "pipeline" in p.lower() and "injects" in p.lower()

    def test_legacy_mode_includes_content_schema(self):
        p = self._prompt(legacy=True)
        assert '"content"' in p

    def test_legacy_mode_does_not_include_ops(self):
        p = self._prompt(legacy=True)
        assert '"ops"' not in p

    def test_section_title_appears_in_both_schemas(self):
        for legacy in (True, False):
            p = self._prompt(legacy=legacy)
            assert "Test Section" in p
