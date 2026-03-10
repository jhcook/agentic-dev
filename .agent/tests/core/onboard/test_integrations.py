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
from agent.core.onboard import integrations

@pytest.fixture
def prompter() -> MagicMock:
    mock = MagicMock(spec=Prompter)
    mock.confirm.return_value = True 
    return mock

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
@patch("agent.core.onboard.integrations.get_secret_manager")
def test_configure_voice_settings(mock_get_manager, mock_config, mock_logger, prompter):
    mock_manager = MagicMock()
    mock_manager.has_secret.return_value = False
    mock_get_manager.return_value = mock_manager
    
    prompter.confirm.return_value = False
    
    integrations.configure_voice_settings(prompter)
    mock_logger.info.assert_called_with("Configuring voice settings", extra={"step": "configure_voice_settings"})

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
@patch("agent.core.onboard.integrations.get_secret_manager")
def test_configure_notion_settings(mock_get_manager, mock_config, mock_logger, prompter):
    prompter.confirm.return_value = False
    with patch("agent.core.onboard.integrations.get_secret", return_value=None):
        integrations.configure_notion_settings(prompter)
    mock_logger.info.assert_called_with("Configuring Notion workspace settings", extra={"step": "configure_notion_settings"})

@patch("agent.core.onboard.integrations.logger")
@patch("agent.core.onboard.integrations.config")
def test_configure_mcp_settings(mock_config, mock_logger, prompter):
    mock_config.get_value.return_value = {}
    prompter.confirm.return_value = False
    
    integrations.configure_mcp_settings(prompter)
    mock_logger.info.assert_called_with("Configuring MCP settings", extra={"step": "configure_mcp_settings"})
