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

def test_tool_registry_importable_from_session_module():
    """Verify AC-1: session.py imports ToolRegistry for unified tool access."""
    import agent.core.session as session_module
    assert hasattr(session_module, "ToolRegistry"), (
        "session module must import ToolRegistry (INFRA-145 AC-1)"
    )


def test_tool_registry_list_tools_returns_callables():
    """Verify ToolRegistry.list_tools() returns actual callable tools."""
    registry = ToolRegistry()
    tools = registry.list_tools()
    assert len(tools) > 0, "ToolRegistry must return at least one tool"
    assert all(callable(t) for t in tools), "All tools must be callable"
