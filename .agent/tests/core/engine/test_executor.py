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
from unittest.mock import MagicMock, AsyncMock

from agent.core.engine.executor import AgentExecutor, MaxStepsExceeded
from agent.core.mcp.client import Tool

@pytest.mark.anyio
async def test_executor_run_loop():
    # Mocks
    mock_llm = MagicMock()
    mock_mcp = AsyncMock()
    
    # Setup Tools
    mock_mcp.list_tools.return_value = [
        Tool(name="search", description="Search web", inputSchema={})
    ]
    
    # Setup LLM responses for the loop
    # 1. Thought -> Action
    # 2. Thought -> Finish
    
    response_1 = """Thought: Look up data.
Action: { "tool": "search", "tool_input": {"query": "foo"} }"""

    response_2 = """Thought: I have the data.
Action: { "tool": "Final Answer", "tool_input": "The answer is bar" }"""

    # We need to mock AIService.complete
    # Since executor runs it in thread, we mock the sync method
    mock_llm.complete.side_effect = [response_1, response_2]
    
    # Mock Tool Execution
    mock_mcp.call_tool.return_value = "Search Result: foo is bar"
    
    executor = AgentExecutor(llm=mock_llm, mcp_client=mock_mcp, max_steps=5)
    
    # run() is an async generator — collect events
    events = []
    async for event in executor.run("What is foo?"):
        events.append(event)
    
    # Find the final answer event
    final = [e for e in events if e.get("type") == "final_answer"]
    assert len(final) == 1
    assert final[0]["content"] == "The answer is bar"
    assert mock_llm.complete.call_count == 2
    mock_mcp.call_tool.assert_called_with("search", {"query": "foo"})

@pytest.mark.anyio
async def test_max_steps_exceeded():
    mock_llm = MagicMock()
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = []
    
    # Always return action (never finishes)
    mock_llm.complete.return_value = 'Action: { "tool": "loop", "tool_input": {} }'
    mock_mcp.call_tool.return_value = "looping"
    
    executor = AgentExecutor(llm=mock_llm, mcp_client=mock_mcp, max_steps=2)
    
    with pytest.raises(MaxStepsExceeded):
        async for _ in executor.run("Go"):
            pass


@pytest.mark.anyio
async def test_model_propagation():
    """Verify the model parameter is forwarded to llm.complete()."""
    mock_llm = MagicMock()
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = []

    # Immediate finish so we only need one LLM call
    mock_llm.complete.return_value = 'The answer is done.'

    executor = AgentExecutor(
        llm=mock_llm, mcp_client=mock_mcp, max_steps=5, model="gemini-2.5-pro"
    )

    async for _ in executor.run("Hello"):
        pass

    # Verify model= was passed in the complete call
    call_kwargs = mock_llm.complete.call_args
    assert call_kwargs is not None
    # Check keyword arg 'model'
    assert "model" in call_kwargs.kwargs or (
        len(call_kwargs.args) > 1 and call_kwargs.args[1] == "gemini-2.5-pro"
    ), f"model not propagated: {call_kwargs}"
