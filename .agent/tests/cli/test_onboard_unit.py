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

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.onboard import (
    app as onboard_app,
    check_dependencies,
    configure_api_keys,
    ensure_agent_directory,
    ensure_gitignore,
)

runner = CliRunner()

@patch("shutil.which")
def test_check_dependencies_success(mock_which):
    """Tests that check_dependencies passes when all binaries are found."""
    mock_which.return_value = "/usr/bin/some_path"
    try:
        check_dependencies()
    except typer.Exit:
        pytest.fail("check_dependencies raised Exit unexpectedly.")

    assert mock_which.call_count >= 1
    mock_which.assert_any_call("git")

@patch("shutil.which")
def test_check_dependencies_failure(mock_which):
    """Tests that check_dependencies raises an error if a binary is missing."""
    mock_which.side_effect = lambda cmd: None if cmd == "git" else "/usr/bin/mock"
    
    with pytest.raises(typer.Exit) as excinfo:
        check_dependencies()
    assert excinfo.value.exit_code == 1

def test_ensure_agent_directory_success(tmp_path: Path):
    """Tests that ensure_agent_directory creates the .agent directory."""
    workspace_dir = tmp_path / ".agent"
    assert not workspace_dir.exists()
    ensure_agent_directory(tmp_path)
    assert workspace_dir.is_dir()

def test_ensure_agent_directory_is_file_error(tmp_path: Path):
    """Tests that ensure_agent_directory fails if .agent is a file."""
    workspace_file = tmp_path / ".agent"
    workspace_file.touch()
    with pytest.raises(typer.Exit) as excinfo:
        ensure_agent_directory(tmp_path)
    assert excinfo.value.exit_code == 1

def test_ensure_gitignore_creates_file(tmp_path: Path):
    """Tests that ensure_gitignore creates .gitignore if it's missing."""
    gitignore_path = tmp_path / ".gitignore"
    ensure_gitignore(tmp_path)
    assert gitignore_path.is_file()
    assert ".env" in gitignore_path.read_text()

def test_ensure_gitignore_appends_to_existing(tmp_path: Path):
    """Tests that ensure_gitignore appends .env to an existing file."""
    gitignore_path = tmp_path / ".gitignore"
    initial_content = "node_modules/\n"
    gitignore_path.write_text(initial_content)
    ensure_gitignore(tmp_path)
    final_content = gitignore_path.read_text()
    assert initial_content in final_content
    assert ".env" in final_content

def test_ensure_gitignore_does_not_duplicate(tmp_path: Path):
    """Tests that ensure_gitignore doesn't add .env if it already exists."""
    initial_content = "node_modules/\n.env\n"
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(initial_content)
    ensure_gitignore(tmp_path)
    assert gitignore_path.read_text() == initial_content

@patch("os.chmod")
@patch("getpass.getpass")
@patch("agent.commands.secret._validate_password_strength", return_value=True)
def test_configure_api_keys_creates_new(mock_validate, mock_getpass, mock_chmod, tmp_path: Path, monkeypatch):
    """Tests creating a new secret store with user input."""
    monkeypatch.chdir(tmp_path)
    mock_getpass.side_effect = ["strong_pass", "strong_pass", "test_openai_key"]
    (tmp_path / ".agent").mkdir(exist_ok=True)
    configure_api_keys()
    secrets_dir = tmp_path / ".agent" / "secrets"
    assert secrets_dir.is_dir()
    mock_chmod.assert_called()

@patch("shutil.which")
@patch("getpass.getpass")
@patch("agent.commands.secret._validate_password_strength", return_value=True)
def test_onboard_command_success_flow(mock_validate, mock_getpass, mock_which):
    """Tests the full `onboard` command in an ideal scenario."""
    mock_which.return_value = "/usr/bin/mock"
    mock_getpass.side_effect = ["pass", "pass", "test_openai_key"]
    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        result = runner.invoke(onboard_app, catch_exceptions=False)
        assert result.exit_code == 0
        assert "Onboarding complete!" in result.output
        assert (fs_path / ".agent").is_dir()

@patch("shutil.which")
def test_onboard_command_fails_on_missing_dependency(mock_which):
    """Tests that the `onboard` command fails if a dependency is missing."""
    mock_which.return_value = None
    with runner.isolated_filesystem():
        result = runner.invoke(onboard_app)
        assert result.exit_code != 0
        assert "Dependency not found" in result.output