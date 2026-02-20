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
from unittest.mock import patch

import pytest

from agent.commands.gates import (
    GateResult,
    log_skip_audit,
    run_docs_check,
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
        assert "Exit code" in result.details

    def test_missing_command(self):
        result = run_qa_gate("nonexistent_command_xyz_12345")
        assert result.passed is False

    def test_default_command(self):
        """Verify default test command is 'make test'."""
        # We just check the function accepts no args
        # (don't actually run make test here)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = run_qa_gate()
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == "make test"


# ── Docs Check ────────────────────────────────────────────────


class TestRunDocsCheck:
    def test_documented_functions_pass(self, clean_py_file: Path):
        result = run_docs_check([clean_py_file])
        assert result.passed is True
        assert result.name == "Documentation Check"

    def test_undocumented_functions_blocked(self, bad_py_file: Path):
        result = run_docs_check([bad_py_file])
        assert result.passed is False
        assert "undocumented" in result.details

    def test_private_functions_ignored(self, tmp_path: Path):
        """Private functions (starting with _) should not be checked."""
        f = tmp_path / "private.py"
        f.write_text(
            "def _helper():\n"
            "    return 42\n"
        )
        result = run_docs_check([f])
        assert result.passed is True

    def test_no_python_files(self, tmp_path: Path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        result = run_docs_check([txt])
        assert result.passed is True
        assert "No Python files" in result.details

    def test_empty_file_list(self):
        result = run_docs_check([])
        assert result.passed is True


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
        docs = run_docs_check([clean_py_file])

        results = [sec, qa, docs]
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
