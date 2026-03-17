# Copyright 2026 Agentic Authors
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

"""Unit and integration tests for execution guardrails."""


import pytest
from agent.core.implement.guards import ExecutionGuardrail

def test_max_iterations_threshold():
    """
    Verify that the guardrail terminates exactly at the max_iterations limit.
    """
    limit = 5
    guard = ExecutionGuardrail(max_iterations=limit)
    
    # Run up to the limit
    for i in range(limit):
        aborted, reason = guard.check_and_record(f"tool_{i}", {"val": i})
        assert not aborted, f"Should not abort at iteration {i+1}"
    
    # Exceed the limit
    aborted, reason = guard.check_and_record("final_tool", {})
    assert aborted is True
    assert "Maximum iteration limit" in reason

def test_repeated_call_detection():
    """
    Verify that calling the same tool with same params triggers a loop abort.
    """
    guard = ExecutionGuardrail(max_iterations=10)
    
    # First call
    aborted, _ = guard.check_and_record("calculator", {"expr": "2+2"})
    assert not aborted
    
    # Identical call
    aborted, reason = guard.check_and_record("calculator", {"expr": "2+2"})
    assert aborted is True
    assert "Detected recursive loop" in reason

def test_different_params_no_abort():
    """
    Verify that the same tool with different parameters does NOT trigger a loop abort.
    """
    guard = ExecutionGuardrail(max_iterations=10)
    
    # Call 1
    aborted, _ = guard.check_and_record("search", {"q": "cats"})
    assert not aborted
    
    # Call 2 (different params)
    aborted, _ = guard.check_and_record("search", {"q": "dogs"})
    assert not aborted

def test_mock_loop_integration():
    """ Integration test simulating a tool loop """
    guard = ExecutionGuardrail(max_iterations=10)
    for _ in range(3):
        aborted, reason = guard.check_and_record("mock_tool", {"action": "loop"})
        if aborted:
            assert "Detected recursive loop" in reason
            break
    assert aborted is True

from unittest.mock import AsyncMock, MagicMock
from agent.core.engine.executor import AgentExecutor
from agent.core.engine.typedefs import AgentAction


def test_excluded_tools():
    """Verify that tools in excluded_tools do not trigger loop aborts."""
    guard = ExecutionGuardrail(max_iterations=10, excluded_tools=["safe_tool"])
    
    # Repeated calls should not abort since safe_tool is excluded
    aborted, _ = guard.check_and_record("safe_tool", {"action": "poll"})
    assert not aborted
    aborted, _ = guard.check_and_record("safe_tool", {"action": "poll"})
    assert not aborted


def test_executor_loop_guardrail_integration():
    """Test that the executor respects the ExecutionGuardrail and yields an error upon loop detection."""
    import asyncio

    async def _run():
        """Run the executor loop guardrail integration test."""
        executor = AgentExecutor(llm=MagicMock(), mcp_client=AsyncMock(), max_steps=10)
        
        # Enable the guardrail manually for the test
        executor.guardrail = ExecutionGuardrail(max_iterations=5)
        
        # Mock parser to return a loop of the same action
        action = AgentAction(tool="fake_tool", tool_input={"query": "test"}, log="thought")
        executor.parser.parse = lambda x: action
        
        # Mock mcp.list_tools
        executor.mcp = AsyncMock()
        executor.mcp.list_tools.return_value = []
        
        events = []
        async for event in executor.run("start"):
            events.append(event)
            if event["type"] == "final_answer":
                break

        # Should see the error event injected
        errors = [e for e in events if e["type"] == "error" and "Execution Guardrail Aborted" in e.get("content", "")]
        assert len(errors) == 1
        assert "recursive loop" in errors[0]["content"]
        
        # Should yield a final answer right after the error if repeating loop
        finals = [e for e in events if e["type"] == "final_answer"]
        assert len(finals) == 1
        assert "forced to terminate due to a repeating tool loop" in finals[0]["content"]

    asyncio.run(_run())

