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

"""Tests for core.implement.orchestrator (AC-7)."""

import pytest

from agent.core.implement.orchestrator import (
    Orchestrator,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
)


class TestParseCodeBlocks:
    """Tests for parse_code_blocks."""

    def test_fenced_language_colon_format(self):
        """Parses ```language:path format."""
        blocks = parse_code_blocks("```python:src/foo.py\ncode here\n```")
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/foo.py"
        assert blocks[0]["content"] == "code here"

    def test_file_header_format(self):
        """Parses 'File: path' header format."""
        blocks = parse_code_blocks("File: src/bar.py\n```python\ncode\n```")
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/bar.py"

    def test_no_blocks_returns_empty(self):
        """Returns empty list when no code blocks found."""
        assert parse_code_blocks("no blocks here") == []


class TestParseSearchReplaceBlocks:
    """Tests for parse_search_replace_blocks."""

    def test_parses_single_block(self):
        """Parses a single search/replace block."""
        content = "File: src/foo.py\n<<<SEARCH\nold line\n===\nnew line\n>>>"
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/foo.py"
        assert blocks[0]["search"] == "old line"
        assert blocks[0]["replace"] == "new line"

    def test_multiple_blocks_same_file(self):
        """Parses multiple blocks under a single file header."""
        content = (
            "File: src/foo.py\n"
            "<<<SEARCH\na\n===\nb\n>>>\n"
            "<<<SEARCH\nc\n===\nd\n>>>"
        )
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 2
        assert all(b["file"] == "src/foo.py" for b in blocks)

    def test_no_blocks_returns_empty(self):
        """Returns empty list when no search/replace blocks found."""
        assert parse_search_replace_blocks("nothing here") == []


class TestSplitRunbookIntoChunks:
    """Tests for split_runbook_into_chunks."""

    def test_splits_on_step_headers(self):
        """Each ### Step N becomes its own chunk."""
        content = (
            "## Overview\npreamble\n"
            "## Implementation Steps\n\n"
            "### Step 1\ncontent1\n"
            "### Step 2\ncontent2"
        )
        global_ctx, chunks = split_runbook_into_chunks(content)
        assert "preamble" in global_ctx
        assert len(chunks) == 2
        assert "Step 1" in chunks[0]
        assert "Step 2" in chunks[1]

    def test_no_impl_header_returns_full_content(self):
        """When no implementation section header found, returns one chunk."""
        _, chunks = split_runbook_into_chunks("# Just a doc\nsome text")
        assert len(chunks) == 1

    def test_dod_appended_as_chunk(self):
        """Definition of Done section is appended as a final chunk."""
        content = (
            "## Implementation Steps\n\n### Step 1\ncode\n"
            "## Definition of Done\n- [ ] CHANGELOG updated"
        )
        _, chunks = split_runbook_into_chunks(content)
        assert any("CHANGELOG" in c for c in chunks)


class TestOrchestrator:
    """Tests for Orchestrator.apply_chunk."""

    def test_apply_chunk_new_file(self, tmp_path, monkeypatch):
        """New-file blocks are written and step_loc is non-zero."""
        monkeypatch.chdir(tmp_path)
        orch = Orchestrator("INFRA-001", yes=True)
        chunk = (
            'File: new_module.py\n'
            '```python\n'
            '"""New module."""\n\n\ndef foo():\n    """Foo."""\n    pass\n'
            '```'
        )
        step_loc, modified = orch.apply_chunk(chunk, step_index=1)
        assert "new_module.py" in modified
        assert step_loc > 0

    def test_apply_chunk_docstring_violation_rejected(self, tmp_path, monkeypatch):
        """Files missing docstrings are added to rejected_files, not written."""
        monkeypatch.chdir(tmp_path)
        orch = Orchestrator("INFRA-001", yes=True)
        chunk = "File: bad_module.py\n```python\ndef foo():\n    pass\n```"
        _, modified = orch.apply_chunk(chunk, step_index=1)
        assert "bad_module.py" in orch.rejected_files
        assert modified == []


class TestParseCodeBlocksRegressions:
    """Regression tests for INFRA-106 parser bugs."""

    def test_modify_header_not_parsed_as_full_file_block(self):
        """[MODIFY] headers must NEVER appear in parse_code_blocks output.

        Regression: previously [MODIFY] leaked into parse_code_blocks because
        the regex included MODIFY in its alternation. This caused files to be
        sent through the docstring gate and rejected even when they had valid
        S/R blocks.
        """
        content = (
            "#### [MODIFY] src/agent/core/check/quality.py\n\n"
            "```\n"
            "<<<SEARCH\n"
            "def check_journey_coverage(\n"
            "===\n"
            "def check_code_quality():\n"
            "    pass\n\n"
            "def check_journey_coverage(\n"
            ">>>\n"
            "```"
        )
        blocks = parse_code_blocks(content)
        # [MODIFY] must not appear here — it belongs to parse_search_replace_blocks
        assert all(b["file"] != "src/agent/core/check/quality.py" for b in blocks)

    def test_new_header_with_search_replace_noop_not_parsed_as_full_file_block(self):
        """[NEW] with a <<<SEARCH no-op block must not appear in parse_code_blocks.

        Regression: when a runbook uses [NEW] with a <<<SEARCH no-op for
        idempotency, parse_code_blocks was treating the <<<SEARCH text as the
        file content, triggering empty-file or docstring-gate failures.
        """
        content = (
            "#### [NEW] scripts/check_loc.py\n\n"
            "```python\n"
            "<<<SEARCH\n"
            "MAX_LOC = 500\n"
            "===\n"
            "MAX_LOC = 500\n"
            ">>>\n"
            "```"
        )
        blocks = parse_code_blocks(content)
        assert all(b["file"] != "scripts/check_loc.py" for b in blocks), (
            "No-op <<<SEARCH block inside [NEW] must not be treated as full-file content"
        )

    def test_new_header_with_sr_blocks_parsed_by_sr_parser(self):
        """[NEW] headers containing real S/R blocks are routed to parse_search_replace_blocks.

        This is the idempotency pattern: a file that may already exist is updated
        in-place via S/R even though the runbook marks it [NEW].
        """
        content = (
            "#### [NEW] scripts/check_loc.py\n\n"
            "```python\n"
            "<<<SEARCH\n"
            "MAX_LOC = 500\n"
            "===\n"
            "MAX_LOC = 500\n"
            ">>>\n"
            "```"
        )
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["file"] == "scripts/check_loc.py"
        assert blocks[0]["search"] == "MAX_LOC = 500"
        assert blocks[0]["replace"] == "MAX_LOC = 500"
