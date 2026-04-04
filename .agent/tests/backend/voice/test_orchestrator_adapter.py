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
from backend.voice.orchestrator import VoiceOrchestrator
from agent.core.adk.tools import ToolRegistry

def test_voice_adapter_initialization():
    """Verify AC-3: VoiceOrchestrator initializes ToolRegistry."""
    orch = VoiceOrchestrator()
    assert hasattr(orch, 'registry'), "VoiceOrchestrator missing registry attribute"
    assert isinstance(orch.registry, ToolRegistry)

def test_voice_get_tools_uses_registry():
    """Verify VoiceOrchestrator delegates tool retrieval to registry."""
    orch = VoiceOrchestrator()
    tools = orch.get_tools()
    # Should match registry output
    assert len(tools) == len(ToolRegistry().list_tools())
