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
Unit tests for agent.tools.shell.

Covers:
- run_command: basic execution, empty command, path traversal rejection,
  absolute-path token sandbox enforcement, background mode
- send_command_input / check_command_status: happy path and missing-process errors
- _validate_path: regression test that the fix (repo_root / path).resolve()
  is the implementation being used (not the unsafe bare Path(path).resolve())
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import shell
from agent.tools.utils import validate_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_bg_processes():
    """Ensure the global background-process store is clean between tests."""
    shell._BACKGROUND_PROCESSES.clear()
    yield
    shell._BACKGROUND_PROCESSES.clear()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# _validate_path regression: must use (repo_root / path).resolve() form
# ---------------------------------------------------------------------------

class TestValidatePath:
    """
    Regression tests for the sandbox fix.

    The old shell.py used ``Path(path).resolve()`` which would resolve a
    relative path against the *process* working directory, not the repo root.
    The correct implementation (via utils.validate_path) uses
    ``(repo_root / path).resolve()``.
    """

    def test_relative_path_resolved_against_repo_root(self, repo):
        """A relative path is treated as relative to repo_root, not CWD."""
        result = validate_path("sub/file.txt", repo)
        assert result == repo / "sub" / "file.txt"

    def test_absolute_inside_repo_accepted(self, repo):
        p = str(repo / "sub" / "file.txt")
        result = validate_path(p, repo)
        assert result == Path(p).resolve()

    def test_traversal_rejected(self, repo):
        with pytest.raises(ValueError, match="outside the repository root"):
            validate_path("../../etc/passwd", repo)

    def test_absolute_outside_repo_rejected(self, repo):
        with pytest.raises(ValueError, match="outside the repository root"):
            validate_path("/etc/passwd", repo)


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_basic_echo(self, repo):
        result = shell.run_command("echo hello", repo)
        assert "hello" in result

    def test_empty_command_rejected(self, repo):
        result = shell.run_command("   ", repo)
        assert result.startswith("Error:")

    def test_path_traversal_rejected(self, repo):
        result = shell.run_command("cat ../../etc/passwd", repo)
        assert result.startswith("Error:")

    def test_absolute_path_outside_repo_rejected(self, repo):
        result = shell.run_command("cat /etc/passwd", repo)
        assert result.startswith("Error:")

    def test_background_returns_id(self, repo):
        result = shell.run_command("sleep 60", repo, background=True)
        assert result.startswith("Command started with ID:")
        # Clean up
        cmd_id = result.split(": ")[1]
        state = shell._BACKGROUND_PROCESSES.get(cmd_id)
        if state:
            state["proc"].kill()
            state["proc"].wait()

    def test_output_scrubbed(self, repo):
        """run_command passes output through scrub_sensitive_data."""
        with patch("agent.tools.shell.scrub_sensitive_data", return_value="SCRUBBED") as mock:
            result = shell.run_command("echo test", repo)
        mock.assert_called_once()
        assert result == "SCRUBBED"


# ---------------------------------------------------------------------------
# send_command_input
# ---------------------------------------------------------------------------

class TestSendCommandInput:
    def test_unknown_id_returns_error(self):
        result = shell.send_command_input("nonexistent-id", "hello")
        assert result.startswith("Error:")

    def test_sends_input_to_running_process(self, repo):
        # Start a background process that reads stdin
        start_result = shell.run_command("cat", repo, background=True)
        cmd_id = start_result.split(": ")[1]
        try:
            result = shell.send_command_input(cmd_id, "ping")
            assert result == "Input sent."
        finally:
            state = shell._BACKGROUND_PROCESSES.get(cmd_id)
            if state:
                state["proc"].kill()
                state["proc"].wait()

    def test_error_on_exited_process(self, repo):
        start_result = shell.run_command("true", repo, background=True)
        cmd_id = start_result.split(": ")[1]
        state = shell._BACKGROUND_PROCESSES[cmd_id]
        state["proc"].wait()  # let it finish
        # Give the thread a moment
        time.sleep(0.1)
        result = shell.send_command_input(cmd_id, "hello")
        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# check_command_status
# ---------------------------------------------------------------------------

class TestCheckCommandStatus:
    def test_unknown_id_returns_error(self):
        result = shell.check_command_status("nonexistent-id")
        assert result.startswith("Error:")

    def test_running_process_status(self, repo):
        start_result = shell.run_command("sleep 60", repo, background=True)
        cmd_id = start_result.split(": ")[1]
        try:
            result = shell.check_command_status(cmd_id)
            assert "Running" in result
        finally:
            state = shell._BACKGROUND_PROCESSES.get(cmd_id)
            if state:
                state["proc"].kill()
                state["proc"].wait()

    def test_exited_process_status(self, repo):
        start_result = shell.run_command("true", repo, background=True)
        cmd_id = start_result.split(": ")[1]
        state = shell._BACKGROUND_PROCESSES[cmd_id]
        state["proc"].wait()
        time.sleep(0.1)
        result = shell.check_command_status(cmd_id)
        assert "Exited" in result


# ---------------------------------------------------------------------------
# interactive_shell (stub)
# ---------------------------------------------------------------------------

class TestInteractiveShell:
    def test_returns_stub_message(self, repo):
        result = shell.interactive_shell(repo)
        assert "not supported" in result.lower()
