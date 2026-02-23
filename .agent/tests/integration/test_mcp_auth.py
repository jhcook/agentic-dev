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

import json
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from agent.commands.mcp import app

runner = CliRunner()

@patch("agent.commands.mcp.Confirm.ask")
def test_mcp_auth_auto_rejection(mock_confirm):
    """Test that rejecting the consent prompt aborts the extraction."""
    mock_confirm.return_value = False
    
    result = runner.invoke(app, ["auth", "notebooklm", "--auto"])
    
    assert result.exit_code == 1

@patch("agent.commands.mcp.subprocess.run")
@patch("agent.commands.mcp.Confirm.ask")
@patch("agent.commands.mcp.SecretManager")
def test_mcp_auth_auto_success(mock_sm_cls, mock_confirm, mock_subprocess_run):
    """Test successful automatic cookie extraction and storage."""
    mock_confirm.return_value = True
    
    # Mock subprocess result
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({
        "status": "success",
        "browser": "Chrome",
        "cookies": {"SID": "123", "HSID": "456", "SSID": "789"}
    })
    mock_subprocess_run.return_value = mock_result
    
    mock_sm = MagicMock()
    mock_sm_cls.return_value = mock_sm
    
    result = runner.invoke(app, ["auth", "notebooklm", "--auto"])
    
    assert result.exit_code == 0
    mock_sm.set_secret.assert_called_once_with(
        "notebooklm_cookies", 
        {"SID": "123", "HSID": "456", "SSID": "789"}
    )
    
@patch("agent.commands.mcp.subprocess.run")
def test_mcp_auth_interactive(mock_subprocess_run):
    """Test standard interactive auth flow."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    
    result = runner.invoke(app, ["auth", "notebooklm"])
    
    assert result.exit_code == 0
    mock_subprocess_run.assert_called_once()
    assert "notebooklm-mcp-auth" in mock_subprocess_run.call_args[0][0]

def test_mcp_auth_no_auto_launch():
    """Test that --no-auto-launch prints instructions and exits."""
    result = runner.invoke(app, ["auth", "notebooklm", "--no-auto-launch"])
    
    assert result.exit_code == 0

@patch("agent.commands.mcp.subprocess.run")
def test_mcp_auth_file(mock_subprocess_run):
    """Test that the --file flag passes the path to the underlying auth tool."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    
    result = runner.invoke(app, ["auth", "notebooklm", "--file", "cookies.json"])
    
    assert result.exit_code == 0
    mock_subprocess_run.assert_called_once()
    
    # Verify the command contains --file and the path
    called_args = mock_subprocess_run.call_args[0][0]
    assert "--file" in called_args
    assert "cookies.json" in called_args
