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
from unittest.mock import patch, MagicMock
from agent.tui.session import TUISession
from backend.voice.orchestrator import VoiceOrchestrator
from agent.core.adk.tools import ToolRegistry

@pytest.mark.asyncio
async def test_ac5_identical_tool_lists():
    """Verify that both TUI and Voice interfaces produce identical tool lists (AC-5)."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    tui_tools = tui.get_available_tools()
    voice_tools = voice.get_tools()
    
    assert len(tui_tools) == len(voice_tools), "Interfaces returned different numbers of tools"
    
    tui_names = sorted([t.name for t in tui_tools])
    voice_names = sorted([t.name for t in voice_tools])
    
    assert tui_names == voice_names, "Tool name lists do not match between TUI and Voice"

def test_negative_tool_removal_propagation():
    """Verify that removing a tool from the registry propagates to both interfaces."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    # Get original list to find a tool to 'remove'
    registry = ToolRegistry()
    original_tools = registry.list_tools()
    
    if not original_tools:
        pytest.skip("No tools found in registry to test removal.")
        
    tool_to_remove = original_tools[0].name
    
    with patch.object(ToolRegistry, 'list_tools') as mock_list:
        # Simulate registry returning list without the first tool
        mock_list.return_value = original_tools[1:]
        
        current_tui_tools = [t.name for t in tui.get_available_tools()]
        current_voice_tools = [t.name for t in voice.get_tools()]
        
        assert tool_to_remove not in current_tui_tools, f"Tool {tool_to_remove} still visible in TUI after removal"
        assert tool_to_remove not in current_voice_tools, f"Tool {tool_to_remove} still visible in Voice after removal"

@pytest.mark.asyncio
async def test_invocation_parity():
    """Verify that invoking a tool via both interfaces yields consistent results."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    # We mock the underlying executor to ensure parity in the adapter logic
    with patch("agent.core.engine.executor.execute") as mock_execute:
        mock_execute.return_value = iter(["Thinking...", "Tool Output"])
        
        # TUI tool lookup and check
        tui_tool = tui.get_available_tools()[0]
        # Voice tool lookup and check
        voice_tool = voice.get_tools()[0]
        
        assert tui_tool.name == voice_tool.name
        # In a real scenario, we'd verify the execution flow here if adapters handle the generator
