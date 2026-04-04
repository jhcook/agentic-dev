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

"""Unit tests for check_projected_syntax (Gate 3.5).

All unit-level tests for the check_projected_syntax function live here.
Integration-level tests (exercising the run_generation_gates pipeline) live in
tests/commands/test_runbook_gates_syntax.py.
"""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from agent.core.implement.guards import check_projected_syntax

# AC-6 path integrity is covered by test_check_projected_syntax_path_traversal_blocked below.
# For non-security unit tests, bypass it so focus stays on syntax logic.
_BYPASS_PATH_CHECK = patch(
    "agent.utils.path_utils.validate_path_integrity", return_value=True
)


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_valid_python(mock_vi, tmp_path):
    """AC-2: Valid Python replacement should pass (return None)."""
    file_path = tmp_path / "valid.py"
    file_path.write_text("def hello():\n    print('hi')", encoding="utf-8")

    result = check_projected_syntax(file_path, "print('hi')", "print('hello world')", root_dir=tmp_path)
    assert result is None


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_invalid_indentation(mock_vi, tmp_path):
    """AC-1: REPLACE that produces an IndentationError should be caught."""
    file_path = tmp_path / "indent_error.py"
    file_path.write_text("def hello():\n    pass", encoding="utf-8")

    result = check_projected_syntax(file_path, "    pass", "print('no indent')", root_dir=tmp_path)

    assert result is not None
    assert "Gate 3.5" in result
    assert "indent_error.py" in result


def test_check_projected_syntax_skip_non_python(tmp_path):
    """AC-3: Non-Python files should be skipped silently (before path check)."""
    file_path = tmp_path / "config.yaml"
    file_path.write_text("key: value", encoding="utf-8")

    result = check_projected_syntax(file_path, "key: value", "invalid:::syntax")
    assert result is None


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_search_missing(mock_vi, tmp_path):
    """AC-5: Missing search text should result in a no-op (pass)."""
    file_path = tmp_path / "missing.py"
    file_path.write_text("x = 1", encoding="utf-8")

    result = check_projected_syntax(file_path, "y = 2", "z = 3", root_dir=tmp_path)
    assert result is None


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_catches_syntax_error(mock_vi, tmp_path):
    """AC-1: SyntaxError (unclosed paren) in REPLACE should surface a correction."""
    target = tmp_path / "expr.py"
    target.write_text("x = 1", encoding="utf-8")

    result = check_projected_syntax(target, "x = 1", "x = (", root_dir=tmp_path)

    assert result is not None
    assert "Gate 3.5" in result
    assert "expr.py" in result


@_BYPASS_PATH_CHECK
@patch("agent.core.implement.guards_apply.logger")
def test_check_projected_syntax_emits_telemetry(mock_logger, mock_vi, tmp_path):
    """Verify that SyntaxError triggers a structured warning log event."""
    file_path = tmp_path / "fail.py"
    file_path.write_text("x = 1", encoding="utf-8")

    result = check_projected_syntax(file_path, "x = 1", "x = (", root_dir=tmp_path)

    assert result is not None, "Expected a correction string, got None"
    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert call_args.args[0] == "projected_syntax_gate_fail"
    extra = call_args.kwargs.get("extra", {})
    assert "file" in extra
    assert "error" in extra


def test_check_projected_syntax_path_traversal_blocked(tmp_path):
    """AC-6: check_projected_syntax blocks paths outside the project root (real validate_path_integrity)."""
    external_path = tmp_path / "secret.py"
    external_path.write_text("password = 'hunter2'", encoding="utf-8")

    # No patch — real validate_path_integrity runs.
    # We simulate traversal: filepath IS inside tmp_path but root_dir is a DIFFERENT directory.
    with tempfile.TemporaryDirectory() as other_root:
        result = check_projected_syntax(
            external_path,
            "password = 'hunter2'",
            "x = 1",
            root_dir=Path(other_root),
        )

    assert result is not None
    assert "Gate 3.5" in result
    assert "outside the project root" in result
