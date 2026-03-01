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

"""Tests for AgentExecutor event streaming via run_agentic_loop (INFRA-088).

Verifies that run_agentic_loop correctly translates executor events
(thought, tool_call, tool_result, final_answer, error) into callbacks.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tui.agentic import run_agentic_loop


class TestAgentExecutorEventsViaLoop:
    """Test that run_agentic_loop correctly translates executor events."""

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_thought_callback_invoked(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            yield {"type": "thought", "content": "I should read the file."}
            yield {"type": "final_answer", "content": "Done."}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_thought = MagicMock()

        await run_agentic_loop(
            system_prompt="sys",
            user_prompt="hello",
            messages=[],
            repo_root=Path("/tmp"),
            provider="gemini",
            on_thought=on_thought,
        )

        on_thought.assert_called_once_with("I should read the file.", 1)

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_multiple_tool_calls(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "openai"
        mock_ai.models = {"openai": "gpt-4o"}

        async def fake_run(user_prompt):
            yield {"type": "tool_call", "tool": "read_file", "input": {"path": "a.py"}}
            yield {"type": "tool_result", "tool": "read_file", "output": "content A"}
            yield {"type": "tool_call", "tool": "grep_search", "input": {"pattern": "foo"}}
            yield {"type": "tool_result", "tool": "grep_search", "output": "line 5: foo"}
            yield {"type": "final_answer", "content": "Found foo in a.py"}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        calls = []
        results = []

        result = await run_agentic_loop(
            system_prompt="sys",
            user_prompt="find foo",
            messages=[],
            repo_root=Path("/tmp"),
            provider="openai",
            on_tool_call=lambda n, a, s: calls.append((n, a)),
            on_tool_result=lambda n, r, s: results.append((n, r)),
        )

        assert result == "Found foo in a.py"
        assert len(calls) == 2
        assert calls[0] == ("read_file", {"path": "a.py"})
        assert calls[1] == ("grep_search", {"pattern": "foo"})
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_empty_response_on_error(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "anthropic"
        mock_ai.models = {"anthropic": "claude-sonnet-4-20250514"}

        async def fake_run(user_prompt):
            yield {"type": "error", "content": "Rate limit exceeded"}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_error = MagicMock()

        result = await run_agentic_loop(
            system_prompt="sys",
            user_prompt="anything",
            messages=[],
            repo_root=Path("/tmp"),
            provider="anthropic",
            on_error=on_error,
        )

        assert result == ""
        on_error.assert_called_once_with("Rate limit exceeded")

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_exception_handled_gracefully(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            raise RuntimeError("Connection reset")
            yield  # noqa: make it a generator

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_error = MagicMock()

        result = await run_agentic_loop(
            system_prompt="sys",
            user_prompt="crash",
            messages=[],
            repo_root=Path("/tmp"),
            provider="gemini",
            on_error=on_error,
        )

        assert result == ""
        on_error.assert_called_once()
        assert "Connection reset" in on_error.call_args[0][0]

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_model_override_applied(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            yield {"type": "final_answer", "content": "ok"}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        await run_agentic_loop(
            system_prompt="sys",
            user_prompt="test",
            messages=[],
            repo_root=Path("/tmp"),
            provider="gemini",
            model="gemini-2.5-flash",
        )

        assert mock_ai.models["gemini"] == "gemini-2.5-flash"

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_provider_switch(self, mock_ai, mock_executor_cls, mock_client_cls):
        mock_ai.provider = "gemini"
        mock_ai.models = {}

        async def fake_run(user_prompt):
            yield {"type": "final_answer", "content": "ok"}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        await run_agentic_loop(
            system_prompt="sys",
            user_prompt="test",
            messages=[],
            repo_root=Path("/tmp"),
            provider="openai",
        )

        mock_ai.set_provider.assert_called_once_with("openai")
