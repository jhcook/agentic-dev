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
Tests for INFRA-096: Safe Implementation Apply.

Covers:
- parse_search_replace_blocks parser
- extract_modify_files / build_source_context (source context injection)
- apply_search_replace_to_file (surgical apply)
- File size guard in apply_change_to_file
- Edge cases (ambiguous match, empty replace, chained blocks)
"""

import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.commands.implement import (
    parse_search_replace_blocks,
    extract_modify_files,
    build_source_context,
    apply_search_replace_to_file,
    apply_change_to_file,
    FILE_SIZE_GUARD_THRESHOLD,
    SOURCE_CONTEXT_MAX_LOC,
    SOURCE_CONTEXT_HEAD_TAIL,
)


# ==============================================================================
# Parser Tests (Tests 1–5)
# ==============================================================================


class TestParseSearchReplaceBlocks:
    """Tests for parse_search_replace_blocks()."""

    def test_single_block(self):
        """Test 1: Single file with one search/replace block."""
        content = """Some preamble text.

File: path/to/file.py
<<<SEARCH
def old_function():
    return 1
===
def new_function():
    return 2
>>>
"""
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]['file'] == 'path/to/file.py'
        assert 'def old_function' in blocks[0]['search']
        assert 'def new_function' in blocks[0]['replace']

    def test_multiple_blocks_per_file(self):
        """Test 2: Single file with two search/replace blocks."""
        content = """
File: path/to/file.py
<<<SEARCH
line_a = 1
===
line_a = 10
>>>

<<<SEARCH
line_b = 2
===
line_b = 20
>>>
"""
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 2
        assert blocks[0]['file'] == 'path/to/file.py'
        assert blocks[1]['file'] == 'path/to/file.py'
        assert blocks[0]['search'] == 'line_a = 1'
        assert blocks[0]['replace'] == 'line_a = 10'
        assert blocks[1]['search'] == 'line_b = 2'
        assert blocks[1]['replace'] == 'line_b = 20'

    def test_multiple_files(self):
        """Test 3: Two files, each with one block."""
        content = """
File: src/alpha.py
<<<SEARCH
alpha = 1
===
alpha = 100
>>>

File: src/beta.py
<<<SEARCH
beta = 2
===
beta = 200
>>>
"""
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 2
        assert blocks[0]['file'] == 'src/alpha.py'
        assert blocks[1]['file'] == 'src/beta.py'

    def test_mixed_with_code_blocks(self):
        """Test 4: Mixed search/replace and traditional code blocks."""
        content = """
File: src/existing.py
<<<SEARCH
old_line = True
===
new_line = False
>>>

File: src/new_file.py
```python
# This is a brand new file
print("hello")
```
"""
        blocks = parse_search_replace_blocks(content)
        # Only search/replace blocks should be returned
        assert len(blocks) == 1
        assert blocks[0]['file'] == 'src/existing.py'

    def test_empty_and_malformed(self):
        """Test 5: No blocks and malformed input."""
        # No search/replace blocks at all
        assert parse_search_replace_blocks("Just plain text.") == []
        assert parse_search_replace_blocks("") == []

        # Missing === separator
        malformed = """
File: bad.py
<<<SEARCH
old code
>>>
"""
        assert parse_search_replace_blocks(malformed) == []


# ==============================================================================
# Source Context Tests (Tests 6–10)
# ==============================================================================


class TestExtractModifyFiles:
    """Tests for extract_modify_files()."""

    def test_standard_markers(self):
        """Test 6: Standard [MODIFY] marker extraction."""
        runbook = """
## Implementation Steps

### Step 1

#### [MODIFY] .agent/src/agent/commands/implement.py

Some instructions here.

#### [MODIFY] .agent/tests/test_foo.py

More instructions.
"""
        result = extract_modify_files(runbook)
        assert result == [
            '.agent/src/agent/commands/implement.py',
            '.agent/tests/test_foo.py',
        ]

    def test_deduplication(self):
        """Test 7: Same file referenced twice — only returned once."""
        runbook = """
## Implementation Steps

### Step 1

#### [MODIFY] .agent/src/agent/commands/implement.py
Step 1 instructions.

#### [MODIFY] .agent/src/agent/commands/implement.py
Step 2 instructions.
"""
        result = extract_modify_files(runbook)
        assert result == ['.agent/src/agent/commands/implement.py']
        assert len(result) == 1


class TestBuildSourceContext:
    """Tests for build_source_context()."""

    def test_small_file(self, tmp_path):
        """Test 8: File under threshold — full content included."""
        test_file = tmp_path / "small.py"
        lines = [f"line_{i} = {i}" for i in range(50)]
        test_file.write_text("\n".join(lines))

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ):
            result = build_source_context([str(test_file)])

        assert "(50 LOC)" in result
        assert "line_0 = 0" in result
        assert "line_49 = 49" in result
        assert "omitted" not in result

    def test_large_file_truncation(self, tmp_path):
        """Test 9: File over threshold — truncated with head/tail."""
        test_file = tmp_path / "large.py"
        lines = [f"line_{i} = {i}" for i in range(500)]
        test_file.write_text("\n".join(lines))

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ):
            result = build_source_context([str(test_file)])

        assert "(500 LOC — truncated)" in result
        # Head lines present
        assert "line_0 = 0" in result
        assert "line_99 = 99" in result
        # Tail lines present
        assert "line_499 = 499" in result
        assert "line_400 = 400" in result
        # Omission marker
        assert "(300 lines omitted)" in result

    def test_missing_file(self, tmp_path, caplog):
        """Test 10: Non-existent file — skipped with warning."""
        with patch(
            'agent.commands.implement.resolve_path',
            return_value=None,
        ):
            with caplog.at_level(logging.WARNING):
                result = build_source_context(["nonexistent.py"])

        assert result == ""
        assert "source_context_skip" in caplog.text


# ==============================================================================
# Apply Tests (Tests 11–14)
# ==============================================================================


class TestApplySearchReplaceToFile:
    """Tests for apply_search_replace_to_file()."""

    def test_happy_path(self, tmp_path):
        """Test 11: Single block, exact match — applied successfully."""
        test_file = tmp_path / "target.py"
        test_file.write_text("def foo():\n    return 1\n")

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [{'search': 'return 1', 'replace': 'return 42'}],
                yes=True,
            )

        assert success is True
        assert "return 42" in content
        assert "return 42" in test_file.read_text()

    def test_no_match_ac6(self, tmp_path):
        """Test 12: Search text not found — returns False, file unchanged (AC-6)."""
        test_file = tmp_path / "target.py"
        original = "def foo():\n    return 1\n"
        test_file.write_text(original)

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [{'search': 'NONEXISTENT TEXT', 'replace': 'whatever'}],
                yes=True,
            )

        assert success is False
        assert content == original
        # File unchanged on disk
        assert test_file.read_text() == original

    def test_multiple_blocks_in_order(self, tmp_path):
        """Test 13: Three blocks applied in sequence."""
        test_file = tmp_path / "target.py"
        test_file.write_text("a = 1\nb = 2\nc = 3\n")

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [
                    {'search': 'a = 1', 'replace': 'a = 10'},
                    {'search': 'b = 2', 'replace': 'b = 20'},
                    {'search': 'c = 3', 'replace': 'c = 30'},
                ],
                yes=True,
            )

        assert success is True
        assert content == "a = 10\nb = 20\nc = 30\n"

    def test_second_block_fails_no_partial_apply(self, tmp_path):
        """Test 14: First block matches, second doesn't — no changes applied."""
        test_file = tmp_path / "target.py"
        original = "a = 1\nb = 2\n"
        test_file.write_text(original)

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [
                    {'search': 'a = 1', 'replace': 'a = 10'},
                    {'search': 'DOES NOT EXIST', 'replace': 'whatever'},
                ],
                yes=True,
            )

        assert success is False
        assert content == original
        # File unchanged on disk — no partial apply
        assert test_file.read_text() == original


# ==============================================================================
# Size Guard Tests (Tests 15–18)
# ==============================================================================


class TestFileSizeGuard:
    """Tests for file size guard in apply_change_to_file()."""

    def test_small_file_accepted(self, tmp_path):
        """Test 15: File under threshold — full-file overwrite accepted."""
        test_file = tmp_path / "small.py"
        lines = [f"line_{i}" for i in range(100)]
        test_file.write_text("\n".join(lines))

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            result = apply_change_to_file(
                str(test_file),
                "new content\n",
                yes=True,
            )

        assert result is True

    def test_large_file_rejected_ac5(self, tmp_path):
        """Test 16: File over threshold — full-file overwrite rejected (AC-5)."""
        test_file = tmp_path / "large.py"
        lines = [f"line_{i}" for i in range(FILE_SIZE_GUARD_THRESHOLD + 1)]
        original = "\n".join(lines)
        test_file.write_text(original)

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ):
            from agent.core.implement.guards import FileSizeGuardViolation
            with pytest.raises(FileSizeGuardViolation):
                apply_change_to_file(
                    str(test_file),
                    "completely new content\n",
                    yes=True,
                )

        # File unchanged
        assert test_file.read_text() == original

    def test_new_file_accepted_ac7(self, tmp_path):
        """Test 17: Non-existent file — full-file content accepted (AC-7)."""
        new_file = tmp_path / "brand_new.py"
        assert not new_file.exists()

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=new_file,
        ):
            result = apply_change_to_file(
                str(new_file),
                "print('hello world')\n",
                yes=True,
            )

        assert result is True
        assert new_file.exists()

    def test_legacy_bypass_ac8(self, tmp_path):
        """Test 18: Large file + legacy_apply=True — overwrite proceeds (AC-5 + AC-8)."""
        test_file = tmp_path / "large.py"
        lines = [f"line_{i}" for i in range(250)]
        test_file.write_text("\n".join(lines))

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            result = apply_change_to_file(
                str(test_file),
                "new content via legacy apply\n",
                yes=True,
                legacy_apply=True,
            )

        assert result is True
        # File was overwritten (content present — may have license header prepended)
        assert "new content via legacy apply" in test_file.read_text()


# ==============================================================================
# Edge Case Tests (Tests 19–21) — Panel Recommendations
# ==============================================================================


class TestEdgeCases:
    """Edge case tests recommended by the Governance Panel."""

    def test_duplicate_match_ambiguous(self, tmp_path, caplog):
        """Test 19: Search text appears twice — first occurrence replaced, warning logged."""
        test_file = tmp_path / "target.py"
        test_file.write_text("x = 1\ny = 2\nx = 1\n")

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            with caplog.at_level(logging.WARNING):
                success, content = apply_search_replace_to_file(
                    str(test_file),
                    [{'search': 'x = 1', 'replace': 'x = 99'}],
                    yes=True,
                )

        assert success is True
        # First occurrence replaced, second unchanged
        assert content == "x = 99\ny = 2\nx = 1\n"
        assert "search_replace_ambiguous" in caplog.text

    def test_empty_replacement_deletion(self, tmp_path):
        """Test 20: Empty replacement — search text deleted."""
        test_file = tmp_path / "target.py"
        test_file.write_text("keep_this\ndelete_this\nkeep_this_too\n")

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [{'search': 'delete_this\n', 'replace': ''}],
                yes=True,
            )

        assert success is True
        assert "delete_this" not in content
        assert "keep_this\nkeep_this_too\n" == content

    def test_overlapping_chained_blocks(self, tmp_path):
        """Test 21: Block 2 search depends on block 1 result — chaining works."""
        test_file = tmp_path / "target.py"
        test_file.write_text("foo = 1\nbaz = 3\n")

        with patch(
            'agent.commands.implement.resolve_path',
            return_value=test_file,
        ), patch(
            'agent.commands.implement.backup_file',
            return_value=tmp_path / "backup",
        ):
            success, content = apply_search_replace_to_file(
                str(test_file),
                [
                    # Block 1: foo -> bar
                    {'search': 'foo = 1', 'replace': 'bar = 1'},
                    # Block 2: searches for 'bar' (result of block 1)
                    {'search': 'bar = 1', 'replace': 'bar = 42'},
                ],
                yes=True,
            )

        assert success is True
        assert content == "bar = 42\nbaz = 3\n"
