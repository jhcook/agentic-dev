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

"""Fully implemented end-to-end journey test for INFRA-077."""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from agent.commands.mcp import app as mcp_app
from agent.sync.cli import app as sync_app

runner = CliRunner()

import sys

@pytest.mark.journey("INFRA-077")
@patch("agent.core.secrets.get_secret")
@patch("agent.commands.mcp.SecretManager")
@patch("agent.commands.mcp.config")
@patch("agent.commands.secret._prompt_password")
@patch("agent.commands.mcp.Confirm.ask")
def test_infra_077(mock_confirm, mock_prompt, mock_config, mock_sm_class, mock_get_secret):
    mock_prompt.return_value = "fake_password"
    mock_confirm.return_value = True
    """
    Test the NotebookLM CLI Authentication flow and Sync caching.
    
    Journey:
    1. Authenticate with an auto browser extraction.
    2. Reset local cache.
    """
    
    # 1. Authenticate
    # Mocking successful cookie extraction by patching subprocess.run
    mock_subprocess_result = MagicMock()
    mock_subprocess_result.stdout = '{"status": "success", "cookies": {"TOKEN": "123"}, "browser": "Chrome"}'
    mock_subprocess_result.returncode = 0
    
    with patch("agent.commands.mcp.subprocess.run", return_value=mock_subprocess_result):
        # Run agent mcp auth notebooklm --auto
        result = runner.invoke(mcp_app, ["auth", "notebooklm", "--auto"], input="y\n")
        assert result.exit_code == 0
        assert mock_sm_class.return_value.set_secret.called

    
    # 2. Sync reset
    with patch("agent.db.client.delete_artifact") as mock_delete:
        mock_delete.return_value = True
        result_reset = runner.invoke(sync_app, ["notebooklm", "--reset"])
        assert result_reset.exit_code == 0
        assert "Successfully reset NotebookLM sync state" in result_reset.stdout
