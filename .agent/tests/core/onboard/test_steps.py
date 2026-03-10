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

from agent.core.onboard.prompter import Prompter
from agent.core.onboard import steps, settings

@pytest.fixture
def prompter() -> MagicMock:
    mock = MagicMock(spec=Prompter)
    # mock confirm to return True by default so tests don't hang if they hit a confirmation
    mock.confirm.return_value = True 
    return mock

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_success(mock_find_spec, mock_which, mock_logger, prompter):
    """Test check_dependencies returns True when all found."""
    mock_which.return_value = "/usr/bin/tool"
    mock_find_spec.return_value = True

    result = steps.check_dependencies(prompter)
    assert result is True
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_missing_binary(mock_find_spec, mock_which, mock_logger, prompter):
    """Test check_dependencies returns False when a binary is missing."""
    mock_find_spec.return_value = True
    
    # Missing git
    def which_side_effect(cmd):
        if cmd == "git":
            return None
        return "/usr/bin/tool"
    
    mock_which.side_effect = which_side_effect

    result = steps.check_dependencies(prompter)
    assert result is False
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_creates_dir(mock_logger, prompter, tmp_path):
    """Test ensure_agent_directory creates a missing directory."""
    expected_dir = tmp_path / ".agent"
    assert not expected_dir.exists()
    
    steps.ensure_agent_directory(prompter, project_root=tmp_path)
    assert expected_dir.is_dir()
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_fails_if_file(mock_logger, prompter, tmp_path):
    """Test ensure_agent_directory exits if .agent is a file."""
    expected_dir = tmp_path / ".agent"
    expected_dir.touch()
    
    steps.ensure_agent_directory(prompter, project_root=tmp_path)
    prompter.exit.assert_called_with(1)
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_gitignore_creates_file(mock_logger, prompter, tmp_path):
    """Test ensure_gitignore creates a .gitignore explicitly."""
    gitignore = tmp_path / ".gitignore"
    assert not gitignore.exists()
    
    steps.ensure_gitignore(prompter, project_root=tmp_path)
    assert gitignore.is_file()
    assert ".env" in gitignore.read_text()
    mock_logger.info.assert_called_with("Ensuring agent metadata is gitignored", extra={"step": "ensure_gitignore"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("agent.core.onboard.steps.subprocess.run")
def test_check_github_auth_success(mock_run, mock_which, mock_logger, prompter):
    mock_which.return_value = "/usr/bin/gh"
    prompter.confirm.return_value = False
    
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_run.return_value = mock_process
    
    result = steps.check_github_auth(prompter)
    assert result is True
    mock_logger.info.assert_called_with("Configuring GitHub Auth", extra={"step": "check_github_auth"})

@patch("agent.core.onboard.settings.logger")
@patch("agent.core.onboard.settings.get_secret_manager")
def test_configure_api_keys_already_initialized(mock_get_manager, mock_logger, prompter):
    mock_manager = MagicMock()
    mock_manager.is_initialized.return_value = True
    mock_manager.is_unlocked.return_value = True
    mock_get_manager.return_value = mock_manager
    
    prompter.confirm.return_value = False
    prompter.getpass.return_value = ""
    
    with patch("agent.core.ai.service.ai_service.reload"):
        settings.configure_api_keys(prompter)
            
    mock_logger.info.assert_called_with("Configuring API keys", extra={"step": "configure_api_keys"})

@patch("agent.core.onboard.settings.logger")
@patch("agent.core.onboard.settings.config")
def test_configure_agent_settings_skip(mock_config, mock_logger, prompter):
    mock_config.get_value.side_effect = ["openai", "gpt-4", "native"]
    prompter.confirm.return_value = False
    
    settings.configure_agent_settings(prompter)
    mock_logger.info.assert_called_with("Configuring Agent defaults", extra={"step": "configure_agent_settings"})

@patch("agent.core.onboard.settings.logger")
@patch("agent.core.onboard.settings.config")
def test_select_default_model(mock_config, mock_logger, prompter):
    config_data = {}
    config_path = MagicMock()
    
    with patch("agent.core.ai.service.ai_service.get_available_models") as mock_get_models:
        mock_get_models.return_value = [{"id": "model-1"}, {"id": "model-2"}]
        prompter.prompt.return_value = "1"
        settings.select_default_model(prompter, "openai", config_data, config_path)
        
    mock_config.set_value.assert_called_with(config_data, "agent.models.openai", "model-1")
    mock_logger.info.assert_called_with("Selecting default model for openai", extra={"step": "select_default_model"})

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
@patch("agent.core.onboard.integrations.get_secret_manager")
def test_configure_voice_settings(mock_get_manager, mock_config, mock_logger, prompter):
    mock_manager = MagicMock()
    mock_manager.has_secret.return_value = False
    mock_get_manager.return_value = mock_manager
    
    prompter.confirm.return_value = False
    
    from agent.core.onboard import integrations
    integrations.configure_voice_settings(prompter)
    mock_logger.info.assert_called_with("Configuring voice settings", extra={"step": "configure_voice_settings"})

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
@patch("agent.core.onboard.integrations.get_secret_manager")
def test_configure_notion_settings(mock_get_manager, mock_config, mock_logger, prompter):
    prompter.confirm.return_value = False
    from agent.core.onboard import integrations
    with patch("agent.core.onboard.integrations.get_secret", return_value=None):
        integrations.configure_notion_settings(prompter)
    mock_logger.info.assert_called_with("Configuring Notion workspace settings", extra={"step": "configure_notion_settings"})

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
def test_configure_mcp_settings(mock_config, mock_logger, prompter):
    mock_config.get_value.return_value = {}
    prompter.confirm.return_value = False
    
    from agent.core.onboard import integrations
    integrations.configure_mcp_settings(prompter)
    mock_logger.info.assert_called_with("Configuring MCP settings", extra={"step": "configure_mcp_settings"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
def test_setup_frontend(mock_which, mock_logger, prompter):
    mock_which.return_value = "/usr/bin/npm"
    with patch("agent.core.onboard.steps.subprocess.run") as mock_run, \
         patch("agent.core.onboard.steps.Path.exists", return_value=True):
        steps.setup_frontend(prompter)
        assert mock_run.called
    mock_logger.info.assert_called_with("Setting up admin console frontend", extra={"step": "setup_frontend"})

@patch("agent.core.onboard.steps.logger")
def test_run_verification(mock_logger, prompter):
    with patch("agent.core.ai.service.AIService.complete") as mock_complete:
        mock_complete.return_value = "Hello World"
        steps.run_verification(prompter)
        mock_complete.assert_called()
    mock_logger.info.assert_called_with("Verifying AI connectivity", extra={"step": "run_verification"})

def test_display_next_steps(prompter):
    steps.display_next_steps(prompter)
    # verify table was printed
    prompter.print_table.assert_called()
