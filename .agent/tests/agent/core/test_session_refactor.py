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
from agent.core.session import AgentSession
from agent.core.adk.tools import ToolRegistry

def test_session_initializes_via_registry():
    """Verify AC-1: AgentSession no longer creates tools directly."""
    with patch("agent.core.adk.tools.ToolRegistry.list_tools") as mock_list:
        mock_list.return_value = [MagicMock(name="registry_tool")]
        
        session = AgentSession()
        session._initialize_tools()
        
        mock_list.assert_called_once()
        assert len(session.tools) == 1
        assert session.tools[0]._mock_name == "registry_tool"
