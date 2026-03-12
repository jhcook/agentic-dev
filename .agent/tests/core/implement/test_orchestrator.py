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

from agent.core.implement.orchestrator import Orchestrator
from agent.core.implement.parser import (
    detect_malformed_modify_blocks,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
    validate_runbook_schema,
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


class TestDetectMalformedModifyBlocks:
    """Tests for detect_malformed_modify_blocks — the silent no-op sentinel."""

    def test_detects_modify_with_full_code_block_no_sr(self):
        """Flags [MODIFY] + full code block with no <<<SEARCH as malformed.

        This is the exact pattern that was previously a silent no-op:
        parse_code_blocks excluded [MODIFY] and parse_search_replace_blocks
        found no <<<SEARCH, so the file was transparently skipped.
        """
        content = (
            "#### [MODIFY] src/agent/commands/check.py\n\n"
            "```python\n"
            "def some_fn():\n"
            "    pass\n"
            "```"
        )
        malformed = detect_malformed_modify_blocks(content)
        assert "src/agent/commands/check.py" in malformed

    def test_clean_modify_with_sr_block_not_flagged(self):
        """A correctly-formatted [MODIFY] + S/R block is not flagged."""
        content = (
            "#### [MODIFY] src/agent/commands/check.py\n\n"
            "```\n"
            "<<<SEARCH\n"
            "old code\n"
            "===\n"
            "new code\n"
            ">>>\n"
            "```"
        )
        malformed = detect_malformed_modify_blocks(content)
        assert malformed == []

    def test_new_block_not_flagged(self):
        """[NEW] + full code block is valid and must never be flagged."""
        content = (
            "#### [NEW] scripts/check_loc.py\n\n"
            "```python\n"
            '"""Module docstring."""\n\n'
            "def main():\n"
            '    """Entry point."""\n'
            "    pass\n"
            "```"
        )
        malformed = detect_malformed_modify_blocks(content)
        assert malformed == []

    def test_empty_content_not_flagged(self):
        """Empty string produces no false positives."""
        assert detect_malformed_modify_blocks("") == []


class TestValidateRunbookSchema:
    """Tests for validate_runbook_schema — the pre-flight structural validator."""

    VALID_RUNBOOK = (
        "## Implementation Steps\n\n"
        "### Step 1: Add something\n\n"
        "#### [MODIFY] src/agent/commands/check.py\n\n"
        "```\n<<<SEARCH\nold code\n===\nnew code\n>>>\n```\n\n"
        "### Step 2: Create script\n\n"
        "#### [NEW] scripts/check_loc.py\n\n"
        "```python\n\"\"\"Module.\"\"\"\ndef main():\n    \"\"\"Run.\"\"\"\n    pass\n```\n\n"
        "### Step 3: Remove old\n\n"
        "#### [DELETE] scripts/old.py\n\n"
        "<!-- Replaced by scripts/check_loc.py per INFRA-106 -->\n"
    )

    def test_valid_runbook_returns_no_violations(self):
        """A correctly-formatted runbook produces zero violations."""
        violations = validate_runbook_schema(self.VALID_RUNBOOK)
        assert violations == [], f"Unexpected violations: {violations}"

    def test_missing_implementation_steps_section(self):
        """Runbook with no ## Implementation Steps section fails immediately."""
        content = "## Goal Description\n\nDo something.\n"
        violations = validate_runbook_schema(content)
        assert any("Implementation Steps" in v for v in violations)

    def test_modify_without_sr_block_is_violation(self):
        """[MODIFY] with a full code block but no <<<SEARCH is a violation."""
        content = (
            "## Implementation Steps\n\n"
            "#### [MODIFY] src/agent/core/check/quality.py\n\n"
            "```python\n"
            "def new_fn():\n"
            "    pass\n"
            "```\n"
        )
        violations = validate_runbook_schema(content)
        assert any("MODIFY" in v and "quality.py" in v for v in violations)

    def test_new_without_code_fence_is_violation(self):
        """[NEW] block with no fenced code block is a violation."""
        content = (
            "## Implementation Steps\n\n"
            "#### [NEW] scripts/check_loc.py\n\n"
            "Just some prose, no code block.\n"
        )
        violations = validate_runbook_schema(content)
        assert any("NEW" in v and "check_loc.py" in v for v in violations)

    def test_new_with_sr_fence_is_not_a_violation(self):
        """[NEW] + fenced <<<SEARCH block (idempotency pattern) is valid schema."""
        content = (
            "## Implementation Steps\n\n"
            "#### [NEW] scripts/check_loc.py\n\n"
            "```python\n"
            "<<<SEARCH\n"
            "MAX_LOC = 500\n"
            "===\n"
            "MAX_LOC = 500\n"
            ">>>\n"
            "```\n"
        )
        # The fence is present — schema is valid (the S/R noop is handled at parse time)
        violations = validate_runbook_schema(content)
        assert not any("check_loc.py" in v for v in violations)

    def test_delete_without_rationale_is_violation(self):
        """[DELETE] block with no body is a violation."""
        content = (
            "## Implementation Steps\n\n"
            "#### [DELETE] scripts/old.py\n\n"
            "#### [MODIFY] src/foo.py\n\n"
            "```\n<<<SEARCH\nold\n===\nnew\n>>>\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert any("DELETE" in v and "old.py" in v for v in violations)

    def test_multiple_violations_all_reported(self):
        """All violations in a runbook are returned, not just the first."""
        content = (
            "## Implementation Steps\n\n"
            "#### [MODIFY] src/a.py\n\n"
            "```python\ndef a(): pass\n```\n"  # missing <<<SEARCH
            "#### [NEW] scripts/b.py\n\n"
            "Just prose.\n"  # missing code fence
        )
        violations = validate_runbook_schema(content)
        assert len(violations) >= 2
