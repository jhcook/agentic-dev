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

class MockProvider:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        
    async def stream(self, prompt, system_prompt, tools=None, **kwargs) -> AsyncGenerator[str, None]:
        if self.should_fail:
            raise ConnectionError("Mock AI Provider connection failed")
            
        yield "Hello"
        yield " "
        yield "World"

@pytest.mark.asyncio
async def test_agent_session_stream_interaction():
    provider = MockProvider(should_fail=False)
    session = AgentSession(
        provider=provider,
        system_prompt="You are a helpful assistant.",
        tools=[{"name": "test_tool", "description": "A test tool"}],
        tool_handlers={"test_tool": lambda: "test"}
    )
    
    chunks = []
    async for chunk in session.stream_interaction("Say hello"):
        chunks.append(chunk)
        
    assert "".join(chunks) == "Hello World"
    assert len(session.history) == 2
    assert session.history[0] == {"role": "user", "content": "Say hello"}
    assert session.history[1] == {"role": "assistant", "content": "Hello World"}

@pytest.mark.asyncio
async def test_agent_session_negative_error_handling():
    provider = MockProvider(should_fail=True)
    session = AgentSession(
        provider=provider,
        system_prompt="You are a helpful assistant.",
        tools=[],
        tool_handlers={}
    )
    
    with pytest.raises(ConnectionError, match="Mock AI Provider connection failed"):
        async for _ in session.stream_interaction("Fail test"):
            pass
