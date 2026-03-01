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

"""Tests for the agentic bridge module (INFRA-088).

Verifies provider function-calling detection and the async run_agentic_loop
bridge to AgentExecutor.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tui.agentic import (
    FUNCTION_CALLING_PROVIDERS,
    LocalToolClient,
    supports_function_calling,
)


class TestSupportsFunctionCalling:
    """Test provider function-calling detection."""

    def test_gemini_supported(self):
        assert supports_function_calling("gemini") is True

    def test_vertex_supported(self):
        assert supports_function_calling("vertex") is True

    def test_openai_supported(self):
        assert supports_function_calling("openai") is True

    def test_anthropic_supported(self):
        assert supports_function_calling("anthropic") is True

    def test_gh_not_supported(self):
        assert supports_function_calling("gh") is False

    def test_ollama_not_supported(self):
        assert supports_function_calling("ollama") is False

    def test_unknown_not_supported(self):
        assert supports_function_calling("nonexistent") is False


class TestFunctionCallingProviders:
    """Test the FUNCTION_CALLING_PROVIDERS constant."""

    def test_is_a_set(self):
        assert isinstance(FUNCTION_CALLING_PROVIDERS, set)

    def test_contains_expected_providers(self):
        expected = {"gemini", "vertex", "openai", "anthropic"}
        assert FUNCTION_CALLING_PROVIDERS == expected


class TestLocalToolClient:
    """Test the LocalToolClient adapter."""

    @pytest.fixture
    def repo(self, tmp_path):
        """Set up a minimal repo structure for LocalToolClient."""
        (tmp_path / ".agent" / "adrs").mkdir(parents=True)
        (tmp_path / ".agent" / "cache" / "journeys").mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_lists_all_expected_tools(self, repo):
        """@QA: Should register 10 tools (5 read-only + 5 interactive)."""
        client = LocalToolClient(repo_root=repo)
        tools = await client.list_tools()
        names = {t.name for t in tools}
        # 5 read-only tools
        assert "read_file" in names
        assert "search_codebase" in names
        assert "list_directory" in names
        assert "read_adr" in names
        assert "read_journey" in names
        # 5 interactive tools
        assert "edit_file" in names
        assert "run_command" in names
        assert "find_files" in names
        assert "grep_search" in names
        assert "patch_file" in names
        assert len(tools) == 10

    @pytest.mark.asyncio
    async def test_tool_schema_structure(self, repo):
        """@QA: Each tool should have valid JSON Schema metadata."""
        client = LocalToolClient(repo_root=repo)
        tools = await client.list_tools()
        for tool in tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"
            assert "properties" in tool.inputSchema
            assert "required" in tool.inputSchema

    @pytest.mark.asyncio
    async def test_call_read_file(self, repo):
        (repo / "test.txt").write_text("hello world")
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("read_file", {"path": "test.txt"})
        assert "hello world" in result.content

    @pytest.mark.asyncio
    async def test_call_edit_file(self, repo):
        """@QA: edit_file should create/overwrite files."""
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("edit_file", {
            "path": "new_file.txt",
            "content": "created by test",
        })
        assert (repo / "new_file.txt").read_text() == "created by test"

    @pytest.mark.asyncio
    async def test_call_list_directory(self, repo):
        (repo / "subdir").mkdir()
        (repo / "subdir" / "a.py").write_text("")
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("list_directory", {"path": "subdir"})
        assert "a.py" in result.content

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, repo):
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("nonexistent", {})
        assert "not found" in result.content

    @pytest.mark.asyncio
    async def test_call_tool_bad_args(self, repo):
        """@QA: Should return error message, not raise exception."""
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("read_file", {"wrong_param": "x"})
        assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_call_tool_string_argument(self, repo):
        """@QA: String arguments should be wrapped as dict."""
        client = LocalToolClient(repo_root=repo)
        result = await client.call_tool("nonexistent", "raw_string")
        assert "not found" in result.content


class TestRunAgenticLoop:
    """Test the async run_agentic_loop bridge."""

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_yields_final_answer(self, mock_ai, mock_executor_cls, mock_client_cls):
        from agent.tui.agentic import run_agentic_loop

        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            yield {"type": "final_answer", "content": "The answer is 42."}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_final = MagicMock()
        result = await run_agentic_loop(
            system_prompt="You are helpful.",
            user_prompt="What is the answer?",
            messages=[],
            repo_root=Path("/tmp/test"),
            provider="gemini",
            on_final_answer=on_final,
        )

        assert result == "The answer is 42."
        on_final.assert_called_once_with("The answer is 42.")

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_yields_tool_call_events(self, mock_ai, mock_executor_cls, mock_client_cls):
        from agent.tui.agentic import run_agentic_loop

        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            yield {"type": "tool_call", "tool": "read_file", "input": {"path": "foo.py"}}
            yield {"type": "tool_result", "tool": "read_file", "output": "file contents"}
            yield {"type": "final_answer", "content": "Done."}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_tool_call = MagicMock()
        on_tool_result = MagicMock()

        result = await run_agentic_loop(
            system_prompt="sys",
            user_prompt="read foo.py",
            messages=[],
            repo_root=Path("/tmp/test"),
            provider="gemini",
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )

        assert result == "Done."
        on_tool_call.assert_called_once_with("read_file", {"path": "foo.py"}, 1)
        on_tool_result.assert_called_once_with("read_file", "file contents", 1)

    @pytest.mark.asyncio
    @patch("agent.tui.agentic.LocalToolClient")
    @patch("agent.tui.agentic.AgentExecutor")
    @patch("agent.tui.agentic.ai_service")
    async def test_handles_error_event(self, mock_ai, mock_executor_cls, mock_client_cls):
        from agent.tui.agentic import run_agentic_loop

        mock_ai.provider = "gemini"
        mock_ai.models = {"gemini": "gemini-2.5-pro"}

        async def fake_run(user_prompt):
            yield {"type": "error", "content": "Something went wrong"}

        mock_executor = MagicMock()
        mock_executor.run = fake_run
        mock_executor_cls.return_value = mock_executor

        on_error = MagicMock()

        result = await run_agentic_loop(
            system_prompt="sys",
            user_prompt="break things",
            messages=[],
            repo_root=Path("/tmp/test"),
            provider="gemini",
            on_error=on_error,
        )

        assert result == ""
        on_error.assert_called_once_with("Something went wrong")


class TestBuildContext:
    """Test _build_context produces valid JSON in ReAct history."""

    def test_tool_input_uses_json_dumps(self):
        """_build_context must emit double-quoted JSON, not Python str()."""
        from agent.core.engine.executor import AgentExecutor
        from agent.core.engine.typedefs import AgentAction, AgentStep

        executor = AgentExecutor(
            llm=MagicMock(),
            mcp_client=MagicMock(),
        )
        step = AgentStep(
            action=AgentAction(
                tool="read_file",
                tool_input={"path": "README.md"},
                log="I need to read the file.",
            ),
            observation="# Title\nSome content.",
        )
        context = executor._build_context("Read the README", [step])

        # Must contain double-quoted JSON, NOT single-quoted Python dicts
        assert '"path": "README.md"' in context
        assert "{'path'" not in context

    def test_string_tool_input_serialized(self):
        """String tool_input should be JSON-serialized too."""
        from agent.core.engine.executor import AgentExecutor
        from agent.core.engine.typedefs import AgentAction, AgentStep

        executor = AgentExecutor(
            llm=MagicMock(),
            mcp_client=MagicMock(),
        )
        step = AgentStep(
            action=AgentAction(
                tool="Final Answer",
                tool_input="The answer is 42",
                log="I know the answer.",
            ),
            observation="Done.",
        )
        context = executor._build_context("What is 42?", [step])
        assert '"The answer is 42"' in context


class TestLoopDetection:
    """Test duplicate tool call detection in AgentExecutor.run."""

    @pytest.mark.asyncio
    async def test_loop_detected_skips_execution(self):
        """When the same tool+input is called twice, skip execution."""
        from agent.core.engine.executor import AgentExecutor
        from agent.core.engine.typedefs import AgentAction, AgentFinish

        mock_llm = MagicMock()
        mock_mcp = MagicMock()
        mock_parser = MagicMock()

        # First call: read_file. Second call: same read_file.
        # Third call: Final Answer.
        read_action = AgentAction(
            tool="read_file",
            tool_input={"path": "test.py"},
            log="Reading test.py",
        )
        final = AgentFinish(
            return_values={"output": "Done."},
            log="I have the answer.",
        )
        mock_parser.parse = MagicMock(side_effect=[read_action, read_action, final])

        # Mock LLM to return anything (parser handles parsing)
        mock_llm.complete = MagicMock(return_value="mock response")

        # Mock tool listing and execution
        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        mock_tool.inputSchema = {"type": "object", "properties": {}, "required": []}

        async def mock_list_tools():
            return [mock_tool]

        mock_result = MagicMock()
        mock_result.content = "file contents here"

        async def mock_call_tool(name, args):
            return mock_result

        mock_mcp.list_tools = mock_list_tools
        mock_mcp.call_tool = mock_call_tool

        executor = AgentExecutor(
            llm=mock_llm,
            mcp_client=mock_mcp,
            parser=mock_parser,
            max_steps=5,
        )

        events = []
        async for event in executor.run("read test.py"):
            events.append(event)

        # Tool should only be called once (second call is loop-detected)
        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        assert len(tool_calls) == 1, f"Expected 1 tool call, got {len(tool_calls)}"

        # Should have a loop detection thought
        thoughts = [e for e in events if e.get("type") == "thought"]
        loop_thoughts = [t for t in thoughts if "Loop detected" in t.get("content", "")]
        assert len(loop_thoughts) == 1

        # Should still reach final answer
        finals = [e for e in events if e.get("type") == "final_answer"]
        assert len(finals) == 1
        assert finals[0]["content"] == "Done."

