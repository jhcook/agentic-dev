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

import pytest
from unittest.mock import MagicMock, patch
from agent.commands.mcp import _get_github_token
from agent.core.secrets import get_secret_manager
from typer import Exit
import os

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure no real GitHub tokens are present in env."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)


@patch("agent.commands.mcp.get_secret")
@patch("agent.commands.mcp.get_secret_manager")
@patch("agent.commands.secret._prompt_password")
@patch("shutil.which")
def test_get_github_token_unlock_flow(mock_which, mock_prompt, mock_get_manager, mock_get_secret):
    mock_which.return_value = None # Disable gh CLI fallback
    # Setup: 
    # 1. First get_secret fails (env empty)
    # 2. Manager is locked
    # 3. Prompt succeeds
    # 4. Manager unlock called
    # 5. Second get_secret succeeds
    
    manager = MagicMock()
    manager.is_initialized.return_value = True
    manager.is_unlocked.return_value = False
    mock_get_manager.return_value = manager
    
    mock_prompt.return_value = "password"
    
    # Side effect for get_secret: fail first call, succeed second call
    # Actually get_secret is called 4 times in the flow roughly
    # 1. token=get_secret("token", "github") -> None
    # 2. token=get_secret("api_key", "gh") -> None
    # 3. Manager logic... manager.get_secret("github", "token") -> "secret_token"
    
    mock_get_secret.side_effect = [None, None] # Initial checks fail
    manager.get_secret.return_value = "secret_token"
    
    token = _get_github_token()
    
    assert token == "secret_token"
    manager.unlock.assert_called_with("password")

@patch("agent.commands.mcp.get_secret")
@patch("agent.commands.mcp.get_secret_manager")
@patch("agent.commands.secret._prompt_password")
@patch("shutil.which")
def test_get_github_token_retry_flow(mock_which, mock_prompt, mock_get_manager, mock_get_secret):
    mock_which.return_value = None
    # Setup: 
    # 1. Manager locked
    # 2. First unlock fails (raises exception)
    # 3. Second unlock succeeds
    
    manager = MagicMock()
    manager.is_initialized.return_value = True
    manager.is_unlocked.return_value = False
    mock_get_manager.return_value = manager
    
    mock_prompt.return_value = "password"
    
    # unlock raises error once, then None (success)
    manager.unlock.side_effect = [Exception("Wrong pass"), None]
    
    mock_get_secret.side_effect = [None, None]
    manager.get_secret.return_value = "secret_token"
    
    token = _get_github_token()
    
    assert token == "secret_token"
    assert manager.unlock.call_count == 2

@patch("agent.commands.mcp.get_secret")
@patch("agent.commands.mcp.get_secret_manager")
@patch("agent.commands.secret._prompt_password")
@patch("shutil.which")
def test_get_github_token_retry_exhausted(mock_which, mock_prompt, mock_get_manager, mock_get_secret):
    mock_which.return_value = None
    # Setup: 
    # 1. Manager locked
    # 2. All 3 unlock attempts fail
    # 3. Should raise Exit
    
    manager = MagicMock()
    manager.is_initialized.return_value = True
    manager.is_unlocked.return_value = False
    mock_get_manager.return_value = manager
    
    mock_prompt.return_value = "password"
    manager.unlock.side_effect = Exception("Wrong pass") # Always fail
    
    mock_get_secret.return_value = None # Fallbacks fail
    
    with pytest.raises(Exit):
        _get_github_token()
        
    assert manager.unlock.call_count == 3
