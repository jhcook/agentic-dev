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

from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from agent.core.onboard import steps, settings

@pytest.fixture
def console() -> Console:
    return Console()

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_success(mock_find_spec, mock_which, mock_logger, console):
    """Test check_dependencies returns True when all found."""
    mock_which.return_value = "/usr/bin/tool"
    mock_find_spec.return_value = True

    result = steps.check_dependencies(console)
    assert result is True
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_missing_binary(mock_find_spec, mock_which, mock_logger, console):
    """Test check_dependencies returns False when a binary is missing."""
    mock_find_spec.return_value = True
    
    # Missing git
    def which_side_effect(cmd):
        if cmd == "git":
            return None
        return "/usr/bin/tool"
    
    mock_which.side_effect = which_side_effect

    result = steps.check_dependencies(console)
    assert result is False
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_creates_dir(mock_logger, console, tmp_path):
    """Test ensure_agent_directory creates a missing directory."""
    expected_dir = tmp_path / ".agent"
    assert not expected_dir.exists()
    
    steps.ensure_agent_directory(console, project_root=tmp_path)
    assert expected_dir.is_dir()
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_fails_if_file(mock_logger, console, tmp_path):
    """Test ensure_agent_directory exits if .agent is a file."""
    expected_dir = tmp_path / ".agent"
    expected_dir.touch()
    
    with pytest.raises(typer.Exit) as excinfo:
        steps.ensure_agent_directory(console, project_root=tmp_path)
    assert excinfo.value.exit_code == 1
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_gitignore_creates_file(mock_logger, console, tmp_path):
    """Test ensure_gitignore creates a .gitignore explicitly."""
    gitignore = tmp_path / ".gitignore"
    assert not gitignore.exists()
    
    steps.ensure_gitignore(console, project_root=tmp_path)
    assert gitignore.is_file()
    assert ".env" in gitignore.read_text()
    mock_logger.info.assert_called_with("Ensuring agent metadata is gitignored", extra={"step": "ensure_gitignore"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("agent.core.onboard.steps.subprocess.run")
@patch("agent.core.onboard.steps.typer.confirm")
def test_check_github_auth_success(mock_confirm, mock_run, mock_which, mock_logger, console):
    mock_which.return_value = "/usr/bin/gh"
    mock_confirm.return_value = False
    
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_run.return_value = mock_process
    
    result = steps.check_github_auth(console)
    assert result is True
    mock_logger.info.assert_called_with("Configuring GitHub Auth", extra={"step": "check_github_auth"})

@patch("agent.core.onboard.settings.logger")
@patch("agent.core.onboard.settings.get_secret_manager")
def test_configure_api_keys_already_initialized(mock_get_manager, mock_logger, console):
    mock_manager = MagicMock()
    mock_manager.is_initialized.return_value = True
    mock_manager.is_unlocked.return_value = True
    mock_get_manager.return_value = mock_manager
    
    # We catch typer.Exit to handle the input prompt failure if the tests are running headless
    with patch("agent.core.onboard.settings.getpass.getpass") as mock_getpass, \
         patch("agent.core.onboard.settings.typer.confirm", return_value=False), \
         patch("agent.core.ai.service.ai_service.reload"):
        mock_getpass.return_value = ""
        try:
            settings.configure_api_keys(console)
        except typer.Exit:
            pass
            
    mock_logger.info.assert_called_with("Configuring API keys", extra={"step": "configure_api_keys"})

@patch("agent.core.onboard.settings.logger")
@patch("agent.core.onboard.settings.config")
@patch("agent.core.onboard.settings.typer.confirm")
def test_configure_agent_settings_skip(mock_confirm, mock_config, mock_logger, console):
    mock_config.get_value.side_effect = ["openai", "gpt-4", "native"]
    mock_confirm.return_value = False
    
    settings.configure_agent_settings(console)
    mock_logger.info.assert_called_with("Configuring Agent defaults", extra={"step": "configure_agent_settings"})
