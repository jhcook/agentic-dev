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

import sys
from unittest.mock import AsyncMock, MagicMock, patch
import unittest
import pytest

# Mock mcp dependency if not installed
try:
    import mcp
except ImportError:
    mcp = MagicMock()
    sys.modules["mcp"] = mcp
    sys.modules["mcp.client"] = MagicMock()
    sys.modules["mcp.client.stdio"] = MagicMock()

from agent.core.mcp.client import MCPClient

class TestMCPClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_params = {
            "command": "npx",
            "args": ["-y", "some-server"],
            "env": {"TEST": "value"}
        }

    async def test_mcp_client_init(self):
        client = MCPClient(**self.mock_params)
        self.assertEqual(client.command, "npx")
        self.assertEqual(client.args, ["-y", "some-server"])
        self.assertEqual(client.env, {"TEST": "value"})
        self.assertEqual(client._full_env["TEST"], "value")

    @patch("agent.core.mcp.client.stdio_client")
    @patch("agent.core.mcp.client.ClientSession")
    async def test_list_tools(self, mock_session_cls, mock_stdio):
        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)
        
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        # Mock list_tools response
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "desc"
        mock_tool.inputSchema = {}
        
        mock_result = MagicMock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_result

        client = MCPClient(**self.mock_params)
        tools = await client.list_tools()
        
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "test_tool")
        self.assertEqual(tools[0].description, "desc")
        mock_session.initialize.assert_awaited_once()

    @patch("agent.core.mcp.client.stdio_client")
    @patch("agent.core.mcp.client.ClientSession")
    async def test_call_tool(self, mock_session_cls, mock_stdio):
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)
        
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_session.call_tool.return_value = "Success"

        client = MCPClient(**self.mock_params)
        result = await client.call_tool("test_tool", {"arg": 1})
        
        self.assertEqual(result, "Success")
        mock_session.call_tool.assert_awaited_once_with("test_tool", {"arg": 1})
