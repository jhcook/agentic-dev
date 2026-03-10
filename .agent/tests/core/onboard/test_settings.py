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
from agent.core.onboard import settings

@pytest.fixture
def prompter() -> MagicMock:
    mock = MagicMock(spec=Prompter)
    mock.confirm.return_value = True 
    return mock

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
