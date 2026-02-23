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
from unittest.mock import patch, MagicMock, AsyncMock
from agent.sync.notebooklm import _sync_notebook, extract_uuid, ensure_notebooklm_sync
import asyncio

def test_extract_uuid():
    """Test UUID extraction from text."""
    text = "Notebook created with ID: 550e8400-e29b-41d4-a716-446655440000 and it's ready."
    assert extract_uuid(text) == "550e8400-e29b-41d4-a716-446655440000"

@pytest.mark.asyncio
@patch("agent.sync.notebooklm.config")
@patch("agent.sync.notebooklm.MCPClient")
@patch("agent.db.client.get_all_artifacts_content")
@patch("agent.db.client.upsert_artifact")
@patch("pathlib.Path.exists")
async def test_notebooklm_sync_execution(mock_exists, mock_upsert, mock_get_content, mock_mcp_cls, mock_config):
    """Test AC-12: The framework actively pushes local rules/ADRs to NotebookLM."""
    
    # Setup Config
    mock_config.load_yaml.return_value = {"agent": {"mcp": {"servers": {"notebooklm": {"command": "test"}}}}}
    mock_config.get_value.return_value = {"notebooklm": {"command": "test"}}
    mock_config.repo_root = MagicMock()
    mock_config.repo_root.name = "test-repo"
    
    mock_adrs_dir = MagicMock()
    mock_config.repo_root.__truediv__.return_value = mock_adrs_dir
    
    mock_exists.return_value = False  # Ignore state file for now
    mock_get_content.return_value = [] # Empty state to force notebook creation
    
    # Mock MCP Client
    mock_mcp = MagicMock()
    mock_mcp_cls.return_value = mock_mcp
    mock_mcp.call_tool = AsyncMock()
    
    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "ID: 123e4567-e89b-12d3-a456-426614174000"
    mock_result.content = [mock_content]
    mock_mcp.call_tool.return_value = mock_result
    
    # Run
    await _sync_notebook()
    
    # Assert
    mock_mcp.call_tool.assert_called()
    calls = mock_mcp.call_tool.call_args_list
    assert len(calls) >= 1
    assert calls[0][0][0] == "notebook_create"
    assert "test-repo" in calls[0][0][1]["title"]
@pytest.mark.asyncio
@patch("agent.db.client.get_all_artifacts_content")
async def test_notebooklm_get_context(mock_get_content):
    """Test get_context integration with NotebookLM."""
    
    # Mock state file content
    mock_get_content.return_value = [{"content": '{"notebook_id": "test-uuid"}'}]
    
    # Mock MCP Client
    from agent.core.mcp.client import MCPClient
    client = MCPClient(command="test")
    client.call_tool = AsyncMock()
    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Retrieved Context"
    mock_result.content = [mock_content]
    client.call_tool.return_value = mock_result
    
    # Run
    result = await client.get_context("test query")
    
    # Assert
    assert result == "Retrieved Context"
    client.call_tool.assert_called_with("notebook_query", {"notebook_id": "test-uuid", "query": "test query"})
