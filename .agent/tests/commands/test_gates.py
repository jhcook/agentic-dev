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

"""Tests for post-apply governance gates (gates.py)."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.commands.gates import (
    GateResult,
    check_commit_message,
    check_commit_size,
    check_domain_isolation,
    log_skip_audit,
    run_qa_gate,
    run_security_scan,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def security_patterns_file(tmp_path: Path) -> Path:
    """Create a minimal security_patterns.yaml for testing."""
    patterns = tmp_path / "security_patterns.yaml"
    patterns.write_text(
        'api_key: "sk-[a-zA-Z0-9]{20,}"\n'
        'eval_exec: "\\\\b(eval|exec)\\\\s*\\\\("\n'
    )
    return patterns


@pytest.fixture
def clean_py_file(tmp_path: Path) -> Path:
    """Create a Python file with docstrings on all public functions."""
    f = tmp_path / "clean.py"
    f.write_text(
        'def hello():\n'
        '    """Say hello."""\n'
        '    return "hello"\n'
    )
    return f


@pytest.fixture
def bad_py_file(tmp_path: Path) -> Path:
    """Create a Python file with a public function missing a docstring."""
    f = tmp_path / "bad.py"
    f.write_text(
        "def undocumented():\n"
        "    return 42\n"
    )
    return f


@pytest.fixture
def insecure_py_file(tmp_path: Path) -> Path:
    """Create a Python file containing a security pattern match."""
    f = tmp_path / "insecure.py"
    f.write_text(
        'result = eval(user_input)\n'
    )
    return f


# ── Security Scan ─────────────────────────────────────────────


class TestRunSecurityScan:
    def test_clean_files_pass(
        self, clean_py_file: Path, security_patterns_file: Path
    ):
        result = run_security_scan([clean_py_file], security_patterns_file)
        assert result.passed is True
        assert result.name == "Security Scan"
        assert result.elapsed_seconds >= 0

    def test_insecure_files_blocked(
        self, insecure_py_file: Path, security_patterns_file: Path
    ):
        result = run_security_scan([insecure_py_file], security_patterns_file)
        assert result.passed is False
        assert "eval_exec" in result.details

    def test_missing_patterns_file_passes(self, clean_py_file: Path, tmp_path: Path):
        """Graceful degradation when patterns file doesn't exist."""
        missing = tmp_path / "nonexistent.yaml"
        result = run_security_scan([clean_py_file], missing)
        assert result.passed is True
        assert "Skipped" in result.details

    def test_empty_file_list(self, security_patterns_file: Path):
        result = run_security_scan([], security_patterns_file)
        assert result.passed is True

    def test_invalid_yaml_patterns(self, clean_py_file: Path, tmp_path: Path):
        bad_yaml = tmp_path / "bad_patterns.yaml"
        bad_yaml.write_text(": invalid: yaml: [\n")
        result = run_security_scan([clean_py_file], bad_yaml)
        assert result.passed is False
        assert "Invalid YAML" in result.details


# ── QA Gate ───────────────────────────────────────────────────


class TestRunQaGate:
    def test_passing_command(self):
        result = run_qa_gate("true")  # Unix `true` always exits 0
        assert result.passed is True
        assert result.name == "QA Validation"

    def test_failing_command(self):
        result = run_qa_gate("false")  # Unix `false` always exits 1
        assert result.passed is False
        assert "exit 1" in result.details

    def test_missing_command(self):
        result = run_qa_gate("nonexistent_command_xyz_12345")
        assert result.passed is False

    def test_default_command(self):
        """Verify default test command is 'pytest .agent/tests'."""
        # We just check the function accepts no args
        # (don't actually run pytest here)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = run_qa_gate()
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == "pytest"


# ── INFRA-137: TestRunDocsCheck removed — enforced at source (INFRA-136). ──


# ── Composability ─────────────────────────────────────────────


class TestGatesComposable:
    def test_all_gates_independent(
        self,
        clean_py_file: Path,
        security_patterns_file: Path,
    ):
        """Each gate can run independently and results are composable."""
        sec = run_security_scan([clean_py_file], security_patterns_file)
        qa = run_qa_gate("true")

        results = [sec, qa]
        assert all(isinstance(r, GateResult) for r in results)
        assert all(r.passed for r in results)
        assert all(r.elapsed_seconds >= 0 for r in results)

    def test_mixed_results(
        self,
        insecure_py_file: Path,
        security_patterns_file: Path,
    ):
        """Gates can return mixed pass/fail independently."""
        sec = run_security_scan([insecure_py_file], security_patterns_file)
        qa = run_qa_gate("true")

        assert sec.passed is False
        assert qa.passed is True


# ── Audit Logging ─────────────────────────────────────────────


class TestLogSkipAudit:
    def test_logs_warning_with_timestamp(self, caplog):
        with caplog.at_level(logging.WARNING):
            log_skip_audit("Security scan")
        assert "[AUDIT]" in caplog.text
        assert "Security scan" in caplog.text

    def test_logs_contain_iso_timestamp(self, caplog):
        with caplog.at_level(logging.WARNING):
            log_skip_audit("QA tests")
        # ISO format includes 'T' separator
        assert "T" in caplog.text


# ── Commit Atomicity Gates (INFRA-091) ────────────────────────


class TestCheckCommitSize:
    """Tests for the check_commit_size gate function."""

    @patch("agent.commands.gates.subprocess.run")
    def test_under_limit(self, mock_run):
        """Under-limit commit passes with total line count in details."""
        mock_run.return_value = MagicMock(returncode=0, stdout="5\t0\tfile.py\n")
        result = check_commit_size()
        assert result.passed is True
        assert "Total: 5 lines" in result.details

    @patch("agent.commands.gates.subprocess.run")
    def test_over_per_file_limit(self, mock_run):
        """Single file exceeding per-file limit triggers warning with filename."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="25\t0\tlarge_file.py\n"
        )
        result = check_commit_size(max_per_file=20)
        assert result.passed is False
        assert "large_file.py: 25 lines (limit 20)" in result.details

    @patch("agent.commands.gates.subprocess.run")
    def test_over_total_limit(self, mock_run):
        """Total lines exceeding threshold triggers warning with total count."""
        output = "\n".join([f"15\t0\tfile{i}.py" for i in range(10)])
        mock_run.return_value = MagicMock(returncode=0, stdout=output)
        result = check_commit_size(max_total=100)
        assert result.passed is False
        assert "Total: 150 lines (limit 100)" in result.details

    @patch("agent.commands.gates.subprocess.run")
    def test_empty_changeset(self, mock_run):
        """Empty changeset passes with zero total."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = check_commit_size()
        assert result.passed is True
        assert "Total: 0 lines" in result.details

    @patch("agent.commands.gates.subprocess.run")
    def test_binary_file_skipped(self, mock_run):
        """Binary files (shown as - - in numstat) are gracefully skipped."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="-\t-\timage.png\n5\t0\tcode.py\n"
        )
        result = check_commit_size()
        assert result.passed is True
        assert "Total: 5 lines" in result.details

    @patch("agent.commands.gates.subprocess.run")
    def test_git_not_available(self, mock_run):
        """Graceful degradation when git is not available."""
        mock_run.side_effect = FileNotFoundError()
        result = check_commit_size()
        assert result.passed is True
        assert "Skipped" in result.details


class TestCheckCommitMessage:
    """Tests for the check_commit_message gate function."""

    def test_valid_single_type(self):
        """Valid conventional commit with scope passes."""
        result = check_commit_message("feat(cli): add new flag")
        assert result.passed is True

    def test_compound_and_message(self):
        """Commit message with 'and' joining two actions fails."""
        result = check_commit_message("feat: add logging and update tests")
        assert result.passed is False
        assert 'contains " and "' in result.details

    def test_missing_prefix(self):
        """Message without conventional commit prefix fails."""
        result = check_commit_message("did some stuff")
        assert result.passed is False
        assert "Missing conventional prefix" in result.details

    def test_empty_message(self):
        """Empty commit message fails."""
        result = check_commit_message("")
        assert result.passed is False
        assert "Empty commit message" in result.details

    def test_word_containing_and(self):
        """Words containing 'and' (e.g. 'command') do not trigger false positive."""
        result = check_commit_message("fix: handle command error")
        assert result.passed is True

    def test_scoped_prefix(self):
        """Scoped conventional prefix (e.g. refactor(core):) is valid."""
        result = check_commit_message("refactor(core): extract helper")
        assert result.passed is True

    def test_and_in_body_line_ignored(self):
        """'and' in multi-line body (line 2+) is exempt — only subject checked."""
        message = "feat: add logging\n\nThis updates and improves tracing"
        result = check_commit_message(message)
        assert result.passed is True


class TestCheckDomainIsolation:
    """Tests for the check_domain_isolation gate function."""

    def test_core_only(self):
        """Core-only changeset passes domain isolation."""
        paths = [Path("src/core/main.py"), Path("src/core/utils.py")]
        result = check_domain_isolation(paths)
        assert result.passed is True

    def test_addons_only(self):
        """Addons-only changeset passes domain isolation."""
        paths = [Path("src/addons/plugin.py"), Path("src/addons/data.json")]
        result = check_domain_isolation(paths)
        assert result.passed is True

    def test_mixed_domains(self):
        """Mixed core and addons changeset fails domain isolation."""
        paths = [Path("src/core/main.py"), Path("src/addons/plugin.py")]
        result = check_domain_isolation(paths)
        assert result.passed is False
        assert "touches both core/ and addons/" in result.details

    def test_no_domain_paths(self):
        """Paths without core/ or addons/ components pass."""
        paths = [Path("README.md"), Path("LICENSE")]
        result = check_domain_isolation(paths)
        assert result.passed is True

    def test_empty_paths(self):
        """Empty file list passes."""
        result = check_domain_isolation([])
        assert result.passed is True
