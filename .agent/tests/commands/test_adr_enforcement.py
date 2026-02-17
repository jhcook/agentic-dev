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

"""Tests for ADR enforcement engine (INFRA-057)."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.lint import (
    _is_suppressed_by_exception,
    lint,
    load_exception_records,
    parse_adr_enforcement_blocks,
    parse_adr_state,
    run_adr_enforcement,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(lint)
    return test_app


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal repo structure with an ADRs dir."""
    adrs = tmp_path / ".agent" / "adrs"
    adrs.mkdir(parents=True)
    return tmp_path


def _make_adr(content_lines):
    """Join lines with newline — avoids textwrap.dedent escape headaches."""
    return "\n".join(content_lines) + "\n"


# ---------------------------------------------------------------------------
# parse_adr_enforcement_blocks
# ---------------------------------------------------------------------------


class TestParseAdrEnforcementBlocks:
    def test_single_lint_rule(self):
        content = _make_adr([
            "# ADR-025",
            "",
            "## Decision",
            "",
            "Some text.",
            "",
            "```enforcement",
            "- type: lint",
            '  pattern: "^from agent"',
            '  scope: "src/*.py"',
            '  violation_message: "Module-level AI import"',
            "```",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "lint"
        assert blocks[0]["pattern"] == "^from agent"
        assert blocks[0]["scope"] == "src/*.py"
        assert blocks[0]["violation_message"] == "Module-level AI import"

    def test_multiple_rules_in_one_block(self):
        content = _make_adr([
            "```enforcement",
            "- type: lint",
            '  pattern: "import os"',
            '  scope: "*.py"',
            '  violation_message: "Do not import os"',
            "- type: lint",
            '  pattern: "import sys"',
            '  scope: "*.py"',
            '  violation_message: "Do not import sys"',
            "```",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert len(blocks) == 2

    def test_single_dict_block(self):
        content = _make_adr([
            "```enforcement",
            "type: lint",
            'pattern: "foo"',
            'scope: "**/*.py"',
            'violation_message: "No foo"',
            "```",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "lint"

    def test_no_enforcement_block(self):
        content = _make_adr([
            "# ADR-099",
            "",
            "## State",
            "",
            "ACCEPTED",
            "",
            "Nothing here.",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert blocks == []

    def test_malformed_yaml_skipped(self):
        content = _make_adr([
            "```enforcement",
            "this is: [not: valid: yaml: {{",
            "```",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert blocks == []

    def test_multiple_enforcement_blocks(self):
        content = _make_adr([
            "```enforcement",
            "- type: lint",
            '  pattern: "foo"',
            '  scope: "*.py"',
            '  violation_message: "No foo"',
            "```",
            "",
            "Some text.",
            "",
            "```enforcement",
            "- type: lint",
            '  pattern: "bar"',
            '  scope: "*.py"',
            '  violation_message: "No bar"',
            "```",
        ])
        blocks = parse_adr_enforcement_blocks(content)
        assert len(blocks) == 2


# ---------------------------------------------------------------------------
# parse_adr_state
# ---------------------------------------------------------------------------


class TestParseAdrState:
    def test_accepted(self):
        content = _make_adr(["# ADR-025", "", "## State", "", "ACCEPTED", "", "## Decision"])
        assert parse_adr_state(content) == "ACCEPTED"

    def test_draft(self):
        content = _make_adr(["# ADR-099", "", "## State", "", "DRAFT", "", "## Decision"])
        assert parse_adr_state(content) == "DRAFT"

    def test_superseded(self):
        content = _make_adr(["# ADR-001", "", "## State", "", "SUPERSEDED", "", "## Decision"])
        assert parse_adr_state(content) == "SUPERSEDED"

    def test_no_state_section(self):
        content = _make_adr(["# ADR-100", "", "No state here."])
        assert parse_adr_state(content) == "UNKNOWN"

    def test_state_with_extra_whitespace(self):
        content = _make_adr(["# ADR-025", "", "## State", "", "  ACCEPTED  ", "", "## Decision"])
        assert parse_adr_state(content) == "ACCEPTED"


# ---------------------------------------------------------------------------
# load_exception_records
# ---------------------------------------------------------------------------


class TestLoadExceptionRecords:
    def test_loads_accepted_exceptions(self, tmp_repo):
        adrs = tmp_repo / ".agent" / "adrs"
        exc_file = adrs / "EXC-001-some-exception.md"
        exc_file.write_text(_make_adr([
            "# EXC-001", "", "## State", "", "ACCEPTED", "", "Exception text.",
        ]))
        exceptions = load_exception_records(adrs)
        assert len(exceptions) == 1
        assert exceptions[0]["id"] == "EXC-001-some-exception"

    def test_ignores_non_accepted_exceptions(self, tmp_repo):
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "EXC-002-draft.md").write_text(
            _make_adr(["# EXC-002", "", "## State", "", "DRAFT"])
        )
        exceptions = load_exception_records(adrs)
        assert len(exceptions) == 0

    def test_no_exception_files(self, tmp_repo):
        adrs = tmp_repo / ".agent" / "adrs"
        assert load_exception_records(adrs) == []


# ---------------------------------------------------------------------------
# _is_suppressed_by_exception
# ---------------------------------------------------------------------------


class TestIsSuppressedByException:
    def test_suppressed_when_both_adr_and_file_referenced(self):
        exceptions = [{
            "id": "EXC-001",
            "content": "Exception for ADR-025 in src/check.py",
            "path": Path("EXC-001.md"),
        }]
        assert _is_suppressed_by_exception("ADR-025", "src/check.py", ".*", exceptions)

    def test_not_suppressed_wrong_adr(self):
        exceptions = [{
            "id": "EXC-001",
            "content": "Exception for ADR-099 in some_file.py",
            "path": Path("EXC-001.md"),
        }]
        assert not _is_suppressed_by_exception("ADR-025", "some_file.py", ".*", exceptions)

    def test_not_suppressed_wrong_file(self):
        exceptions = [{
            "id": "EXC-001",
            "content": "Exception for ADR-025 in other_file.py",
            "path": Path("EXC-001.md"),
        }]
        assert not _is_suppressed_by_exception("ADR-025", "wrong_file.py", ".*", exceptions)

    def test_not_suppressed_empty_exceptions(self):
        assert not _is_suppressed_by_exception("ADR-025", "file.py", ".*", [])


# ---------------------------------------------------------------------------
# run_adr_enforcement
# ---------------------------------------------------------------------------


class TestRunAdrEnforcement:
    def test_no_adrs_dir(self, tmp_path):
        """When no ADRs directory exists, enforcement passes."""
        assert run_adr_enforcement(repo_root=tmp_path) is True

    def test_no_accepted_adrs(self, tmp_repo):
        """When no ACCEPTED ADRs have enforcement blocks, passes."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-099-draft.md").write_text(_make_adr([
            "# ADR-099", "", "## State", "", "DRAFT", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "foo"',
            '  scope: "**/*.py"',
            '  violation_message: "No foo"',
            "```",
        ]))
        assert run_adr_enforcement(repo_root=tmp_repo) is True

    def test_no_enforcement_blocks(self, tmp_repo):
        """ACCEPTED ADR without enforcement blocks passes."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-050-no-rules.md").write_text(
            _make_adr(["# ADR-050", "", "## State", "", "ACCEPTED", "", "No rules here."])
        )
        assert run_adr_enforcement(repo_root=tmp_repo) is True

    def test_violation_detected(self, tmp_repo):
        """Pattern match should produce a violation."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-025-lazy-init.md").write_text(_make_adr([
            "# ADR-025", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "^from agent_core"',
            '  scope: "src/*.py"',
            '  violation_message: "Module-level AI import violates ADR-025"',
            "```",
        ]))
        src_dir = tmp_repo / "src"
        src_dir.mkdir()
        (src_dir / "bad.py").write_text("from agent_core import AIService\n")
        assert run_adr_enforcement(repo_root=tmp_repo) is False

    def test_no_violation_clean_file(self, tmp_repo):
        """File that doesn't match the pattern passes."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-025-lazy-init.md").write_text(_make_adr([
            "# ADR-025", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "^from agent_core"',
            '  scope: "src/*.py"',
            '  violation_message: "Module-level AI import violates ADR-025"',
            "```",
        ]))
        src_dir = tmp_repo / "src"
        src_dir.mkdir()
        (src_dir / "good.py").write_text("# No violating imports\nimport os\n")
        assert run_adr_enforcement(repo_root=tmp_repo) is True

    def test_violation_suppressed_by_exception(self, tmp_repo):
        """Exception record suppresses violation for matching ADR + file."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-025-lazy-init.md").write_text(_make_adr([
            "# ADR-025", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "^from agent_core"',
            '  scope: "src/*.py"',
            '  violation_message: "Module-level AI import violates ADR-025"',
            "```",
        ]))
        (adrs / "EXC-001-allow-ai-import.md").write_text(_make_adr([
            "# EXC-001", "", "## State", "", "ACCEPTED", "",
            "Allows ADR-025 violation in src/legacy.py for backward compatibility.",
        ]))
        src_dir = tmp_repo / "src"
        src_dir.mkdir()
        (src_dir / "legacy.py").write_text("from agent_core import AIService\n")
        assert run_adr_enforcement(repo_root=tmp_repo) is True

    def test_absolute_scope_rejected(self, tmp_repo):
        """Absolute scope path produces a violation."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-030-bad-scope.md").write_text(_make_adr([
            "# ADR-030", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "foo"',
            '  scope: "/etc/passwd"',
            '  violation_message: "Bad scope"',
            "```",
        ]))
        assert run_adr_enforcement(repo_root=tmp_repo) is False

    def test_invalid_regex_reported(self, tmp_repo):
        """Invalid regex pattern produces violation, not crash."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-031-bad-regex.md").write_text(_make_adr([
            "# ADR-031", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "[invalid"',
            '  scope: "*.py"',
            '  violation_message: "Bad regex"',
            "```",
        ]))
        assert run_adr_enforcement(repo_root=tmp_repo) is False

    def test_file_intersection(self, tmp_repo):
        """When explicit file list given, only intersecting files are checked."""
        adrs = tmp_repo / ".agent" / "adrs"
        (adrs / "ADR-040-test.md").write_text(_make_adr([
            "# ADR-040", "", "## State", "", "ACCEPTED", "",
            "```enforcement",
            "- type: lint",
            '  pattern: "forbidden"',
            '  scope: "src/*.py"',
            '  violation_message: "Forbidden found"',
            "```",
        ]))
        src_dir = tmp_repo / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("forbidden\n")
        (src_dir / "b.py").write_text("forbidden\n")
        # Only pass a.py — b.py should NOT be checked
        result = run_adr_enforcement(files=[str(src_dir / "a.py")], repo_root=tmp_repo)
        assert result is False  # a.py still violates


# ---------------------------------------------------------------------------
# lint() CLI: --adr-only flag
# ---------------------------------------------------------------------------


class TestLintAdrOnlyFlag:
    @patch("agent.commands.lint.run_adr_enforcement", return_value=True)
    @patch("agent.commands.lint.get_files_to_lint")
    def test_adr_only_passes(self, mock_get_files, mock_adr, app):
        mock_get_files.return_value = []
        result = runner.invoke(app, ["--adr-only"])
        assert result.exit_code == 0
        assert "ADR enforcement passed" in result.stdout
        mock_adr.assert_called_once()

    @patch("agent.commands.lint.run_adr_enforcement", return_value=False)
    @patch("agent.commands.lint.get_files_to_lint")
    def test_adr_only_fails(self, mock_get_files, mock_adr, app):
        mock_get_files.return_value = []
        result = runner.invoke(app, ["--adr-only"])
        assert result.exit_code == 1
        assert "ADR enforcement failed" in result.stdout

    @patch("agent.commands.lint.run_adr_enforcement", return_value=True)
    @patch("agent.commands.lint.run_ruff", return_value=True)
    @patch("agent.commands.lint.get_files_to_lint")
    def test_adr_runs_alongside_conventional(self, mock_get_files, mock_ruff, mock_adr, app):
        """Without --adr-only, ADR enforcement runs alongside conventional linters."""
        mock_get_files.return_value = ["file.py"]
        result = runner.invoke(app)
        assert result.exit_code == 0
        mock_ruff.assert_called_once()
        mock_adr.assert_called_once()
