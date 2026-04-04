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

"""Unit tests for _extract_runbook_data and validate_runbook_schema."""

import pytest

from agent.core.implement.parser import (
    _extract_runbook_data,
    _unescape_path,
    _mask_fenced_blocks,
    validate_runbook_schema,
    extract_modify_files,
    extract_approved_files,
)


# ── _extract_runbook_data ────────────────────────────────────


class TestExtractRunbookData:
    def test_single_new_block(self):
        content = (
            "# Runbook\n\n"
            "## Implementation Steps\n\n"
            "### Step 1: Create module\n\n"
            "#### [NEW] `mod.py`\n\n"
            "```python\ndef hello(): pass\n```\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        assert steps[0]["title"] == "Create module"
        assert len(steps[0]["operations"]) == 1
        assert steps[0]["operations"][0]["path"] == "mod.py"
        assert "def hello" in steps[0]["operations"][0]["content"]

    def test_modify_block_with_search_replace(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Update config\n\n"
            "#### [MODIFY] `config.py`\n\n"
            "<<<SEARCH\nold_value = 1\n===\nnew_value = 2\n>>>\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op["path"] == "config.py"
        assert len(op["blocks"]) == 1
        assert op["blocks"][0]["search"] == "old_value = 1"
        assert op["blocks"][0]["replace"] == "new_value = 2"

    def test_delete_block(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Remove legacy\n\n"
            "#### [DELETE] `legacy.py`\n\n"
            "No longer needed after migration.\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op["path"] == "legacy.py"
        assert "No longer needed" in op["rationale"]

    def test_multiple_steps(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Create file\n\n"
            "#### [NEW] `a.py`\n\n"
            "```python\nx = 1\n```\n\n"
            "### Step 2: Modify file\n\n"
            "#### [MODIFY] `b.py`\n\n"
            "<<<SEARCH\nold\n===\nnew\n>>>\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 2
        assert steps[0]["title"] == "Create file"
        assert steps[1]["title"] == "Modify file"

    def test_missing_implementation_section_raises(self):
        content = "# Runbook\n\n## Summary\nNo steps here.\n"
        with pytest.raises(ValueError, match="Missing.*Implementation Steps"):
            _extract_runbook_data(content)

    def test_step_with_number_prefix(self):
        """Step titles like 'Step 1: Title' should strip the number prefix."""
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Create the module\n\n"
            "#### [NEW] `mod.py`\n\n"
            "```python\nx = 1\n```\n"
        )
        steps = _extract_runbook_data(content)
        assert steps[0]["title"] == "Create the module"

    def test_multiple_search_replace_in_one_modify(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Update imports\n\n"
            "#### [MODIFY] `main.py`\n\n"
            "<<<SEARCH\nimport old\n===\nimport new\n>>>\n\n"
            "<<<SEARCH\nold.call()\n===\nnew.call()\n>>>\n"
        )
        steps = _extract_runbook_data(content)
        op = steps[0]["operations"][0]
        assert len(op["blocks"]) == 2


# ── validate_runbook_schema ──────────────────────────────────


class TestValidateRunbookSchema:
    def test_valid_runbook_returns_empty_list(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Create module\n\n"
            "#### [NEW] `mod.py`\n\n"
            "```python\ndef hello(): pass\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert violations == []

    def test_missing_implementation_section(self):
        violations = validate_runbook_schema("# Runbook\nNo steps.")
        assert len(violations) == 1
        assert "Implementation Steps" in violations[0]

    def test_empty_search_block_violation(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Fix bug\n\n"
            "#### [MODIFY] `bug.py`\n\n"
            "<<<SEARCH\n   \n===\nfixed\n>>>\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) > 0
        assert any("SEARCH" in v for v in violations)

    def test_modify_with_no_search_blocks(self):
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Fix bug\n\n"
            "#### [MODIFY] `bug.py`\n\n"
            "Just some text without search/replace blocks.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) > 0


# ── _unescape_path (INFRA-148) ──────────────────────────────


class TestUnescapePath:
    def test_empty_string(self):
        assert _unescape_path("") == ""

    def test_plain_path_unchanged(self):
        assert _unescape_path("src/module/main.py") == "src/module/main.py"

    def test_bold_wrapped_path(self):
        """#### [MODIFY] **path/to/file.py** → path/to/file.py"""
        assert _unescape_path("**path/to/file.py**") == "path/to/file.py"

    def test_backslash_escaped_underscores(self):
        r"""#### [MODIFY] src/\_\_init\_\_.py → src/__init__.py"""
        assert _unescape_path(r"src/\_\_init\_\_.py") == "src/__init__.py"

    def test_backtick_wrapped_path(self):
        assert _unescape_path("`config.py`") == "config.py"

    def test_combined_bold_and_escaped(self):
        r"""#### [NEW] **src/\_\_main\_\_.py** → src/__main__.py"""
        assert _unescape_path(r"**src/\_\_main\_\_.py**") == "src/__main__.py"

    def test_whitespace_stripped(self):
        assert _unescape_path("  path/to/file.py  ") == "path/to/file.py"


# ── _mask_fenced_blocks balanced detection (INFRA-148) ──────


class TestMaskFencedBlocksBalanced:
    def test_triple_backtick_masked(self):
        """Standard triple-backtick block is masked."""
        text = "before\n```python\ncode_here\n```\nafter"
        masked = _mask_fenced_blocks(text)
        assert "code_here" not in masked
        assert "before" in masked
        assert "after" in masked

    def test_nested_four_wrapping_three(self):
        """4-backtick fence wrapping inner 3-backtick should NOT close prematurely."""
        text = (
            "before\n"
            "````markdown\n"
            "```python\n"
            "inner_code\n"
            "```\n"
            "````\n"
            "after"
        )
        masked = _mask_fenced_blocks(text)
        # inner_code should be masked (inside the outer 4-backtick fence)
        assert "inner_code" not in masked
        assert "after" in masked

    def test_tilde_fence_masked(self):
        """Tilde fences should also be masked."""
        text = "before\n~~~python\ntilde_code\n~~~\nafter"
        masked = _mask_fenced_blocks(text)
        assert "tilde_code" not in masked
        assert "after" in masked

    def test_headers_inside_fence_not_exposed(self):
        """#### [MODIFY] inside a code fence must not be visible after masking."""
        text = (
            "preamble\n"
            "```\n"
            "#### [MODIFY] fake_header.py\n"
            "<<<SEARCH\nold\n===\nnew\n>>>\n"
            "```\n"
            "real content"
        )
        masked = _mask_fenced_blocks(text)
        assert "[MODIFY]" not in masked
        assert "real content" in masked


# ── Path unescaping in extraction (INFRA-148) ───────────────


class TestPathUnescapingInExtraction:
    def test_extract_runbook_data_unescapes_modify_path(self):
        r"""#### [MODIFY] src/\_\_init\_\_.py extracts as src/__init__.py"""
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Fix init\n\n"
            r"#### [MODIFY] src/\_\_init\_\_.py" + "\n\n"
            "<<<SEARCH\nold = 1\n===\nnew = 2\n>>>\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        assert steps[0]["operations"][0]["path"] == "src/__init__.py"

    def test_extract_runbook_data_unescapes_new_path(self):
        r"""#### [NEW] **src/__main__.py** extracts as src/__main__.py"""
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Create entry\n\n"
            "#### [NEW] **src/__main__.py**\n\n"
            "```python\nprint('hello')\n```\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        assert steps[0]["operations"][0]["path"] == "src/__main__.py"

    def test_extract_modify_files_unescapes(self):
        r"""extract_modify_files returns clean paths."""
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Fix init\n\n"
            r"#### [MODIFY] src/\_\_init\_\_.py" + "\n\n"
            "<<<SEARCH\nold\n===\nnew\n>>>\n"
        )
        files = extract_modify_files(content)
        assert "src/__init__.py" in files

    def test_extract_approved_files_unescapes(self):
        r"""extract_approved_files returns clean paths."""
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Fix init\n\n"
            r"#### [MODIFY] src/\_\_init\_\_.py" + "\n\n"
            "<<<SEARCH\nold\n===\nnew\n>>>\n"
        )
        files = extract_approved_files(content)
        assert "src/__init__.py" in files


# ── Empty SEARCH block detection (INFRA-184) ────────────────


def test_parse_sr_blocks_rejects_empty_search(caplog):
    """AC-4: Verify parse_search_replace_blocks skips whitespace-only SEARCH sections
    and emits the sr_replace_malformed_empty_search structured log event."""
    import logging
    from agent.core.implement.parser import parse_search_replace_blocks

    content = (
        "#### [MODIFY] src/dummy.py\n\n"
        "```\n"
        "<<<SEARCH\n"
        "\n"
        "===\n"
        "new_code()\n"
        ">>>\n"
        "```\n"
    )
    with caplog.at_level(logging.WARNING, logger="agent.core.implement.parser"):
        blocks = parse_search_replace_blocks(content)

    assert len(blocks) == 0, "Empty SEARCH block must be silently rejected"
    assert "sr_replace_malformed_empty_search" in caplog.text
