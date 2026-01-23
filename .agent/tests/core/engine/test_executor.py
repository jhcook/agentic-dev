import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from agent.core.engine.executor import AgentExecutor, MaxStepsExceeded
from agent.core.engine.typedefs import AgentAction, AgentFinish, AgentStep
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
    
    final_answer = await executor.run("What is foo?")
    
    assert final_answer == "The answer is bar"
    assert mock_llm.complete.call_count == 2
    mock_mcp.call_tool.assert_called_with("search", {"query": "foo"})

@pytest.mark.anyio
async def test_max_steps_exceeded():
    mock_llm = MagicMock()
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = []
    
    # Always return action
    mock_llm.complete.return_value = 'Action: { "tool": "loop", "tool_input": {} }'
    mock_mcp.call_tool.return_value = "looping"
    
    executor = AgentExecutor(llm=mock_llm, mcp_client=mock_mcp, max_steps=2)
    
    with pytest.raises(MaxStepsExceeded):
        await executor.run("Go")
