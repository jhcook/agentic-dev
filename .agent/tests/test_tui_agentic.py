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
from agent.tui.agentic import LocalToolClient

@pytest.mark.asyncio
async def test_tui_adapter_agent_session_integration(tmp_path):
    """
    Test that LocalToolClient correctly acts as an adapter for AgentSession
    by yielding standard JSON schema tools.
    """
    repo = tmp_path
    (repo / ".agent" / "adrs").mkdir(parents=True)
    (repo / ".agent" / "cache" / "journeys").mkdir(parents=True)
    
    with patch("agent.tui.agentic.AgentSession", create=True) as MockSession:
        client = LocalToolClient(repo_root=repo)
        tools = await client.list_tools()
        
        assert len(tools) > 0
        for tool in tools:
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"
            assert "properties" in tool.inputSchema
