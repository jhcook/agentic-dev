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
from agent.tui.session import TUISession
from agent.core.adk.tools import ToolRegistry

def test_tui_session_module_imports_tool_registry():
    """Verify AC-2: tui.session imports ToolRegistry for interface parity."""
    import agent.tui.session as tui_module
    assert hasattr(tui_module, "ToolRegistry"), (
        "tui.session must import ToolRegistry (INFRA-145 AC-2)"
    )


def test_tool_registry_provides_tools_for_tui():
    """Verify ToolRegistry can supply tools to the TUI adapter."""
    registry = ToolRegistry()
    tools = registry.list_tools()
    tool_names = [t.__name__ for t in tools]
    # read_file is a required tool for the TUI console
    assert "read_file" in tool_names, "ToolRegistry must expose read_file for TUI"
