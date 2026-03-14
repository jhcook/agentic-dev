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

from agent.core.implement.parser import _extract_runbook_data, validate_runbook_schema


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
