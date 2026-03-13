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
from typing import AsyncGenerator
from agent.core.session import AgentSession

class DummyProvider:
    async def stream(self, prompt, system_prompt, tools) -> AsyncGenerator[str, None]:
        yield f"Response to {prompt}"

@pytest.mark.asyncio
async def test_integration_agent_session_initialization():
    """Integration Testing: Verify AgentSession can be initialized with dummy tools."""
    provider = DummyProvider()
    session = AgentSession(
        provider=provider,
        system_prompt="Test",
        tools=[{"name": "test"}],
        tool_handlers={"test": lambda: None}
    )
    
    chunks = []
    async for chunk in session.stream_interaction("Hello"):
        chunks.append(chunk)
        
    assert "".join(chunks) == "Response to Hello"


@pytest.mark.asyncio
async def test_parity_agent_session_voice_and_tui():
    """Parity Testing: Verify output consistency between TUI and Voice scenarios."""
    provider = DummyProvider()
    
    tui_session = AgentSession(
        provider=provider,
        system_prompt="TUI",
        tools=[],
        tool_handlers={}
    )
    
    voice_session = AgentSession(
        provider=provider,
        system_prompt="Voice",
        tools=[],
        tool_handlers={}
    )
    
    tui_chunks = [c async for c in tui_session.stream_interaction("Parity")]
    voice_chunks = [c async for c in voice_session.stream_interaction("Parity")]
    
    assert tui_chunks == voice_chunks
