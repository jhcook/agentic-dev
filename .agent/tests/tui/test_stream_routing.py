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

"""Regression tests for TUI stream routing (INFRA-088).

Verifies that _do_stream correctly routes regular chat to simple streaming
and only uses the agentic loop for workflow/role invocations. This test
exists because a regression shipped where ALL chat for function-calling
providers was routed through the agentic ReAct loop, breaking normal
conversation.

Journey refs: JRN-088 steps 1-6 (agentic tools only via workflows)
"""

from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture
def mock_dependencies():
    """Mock heavy dependencies so ConsoleApp can be imported headlessly."""
    mock_store_cls = MagicMock()
    mock_store_inst = MagicMock()
    mock_store_inst.list_sessions.return_value = []
    mock_store_inst.create_session.return_value = MagicMock(
        id="test-session-id",
        title="Test Session",
        messages=[],
        model=None,
    )
    mock_store_inst.get_messages.return_value = []
    mock_store_inst.auto_title = MagicMock()
    mock_store_cls.return_value = mock_store_inst

    mock_ai = MagicMock()
    mock_ai.provider = "gemini"
    mock_ai.model = "gemini-2.5-pro"
    mock_ai.models = {"gemini": "gemini-2.5-pro"}
    mock_ai.set_provider = MagicMock()
    mock_ai.clients = {"gemini": MagicMock()}

    with patch("agent.tui.session.SessionStore", mock_store_cls), \
         patch("agent.core.ai.ai_service", mock_ai), \
         patch("agent.tui.commands.discover_workflows", return_value={"preflight": "Run preflight checks"}), \
         patch("agent.tui.commands.discover_roles", return_value={"security": "Security review"}):
        yield {"store": mock_store_inst, "ai": mock_ai}


class TestStreamRouting:
    """Verify _do_stream routes correctly between simple and agentic paths.

    REGRESSION: Previously all function-calling providers (gemini, vertex,
    openai, anthropic) were routed through the agentic ReAct loop, even for
    regular chat. This broke normal conversation because the LLM didn't
    know it was supposed to output ReAct-format JSON.
    """

    @pytest.mark.asyncio
    async def test_regular_chat_uses_simple_stream(self, mock_dependencies):
        """Regular chat (not a workflow/role) MUST use simple streaming.

        This is the exact regression test for the bug where typing
        'hello' in the console would go through the agentic ReAct loop
        instead of simple streaming.
        """
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            # Patch both stream methods to track which is called
            with patch.object(app, "_do_simple_stream", return_value="Hello!") as mock_simple, \
                 patch.object(app, "_do_agentic_stream", return_value="Hello!") as mock_agentic, \
                 patch.object(app, "_write_assistant_start"), \
                 patch.object(app, "_write_final_answer"):

                # Submit a regular chat message
                app._do_stream("system prompt", "hello world", use_tools=False)
                await pilot.pause()

                # CRITICAL: simple stream must be called, NOT agentic
                mock_simple.assert_called_once()
                mock_agentic.assert_not_called()

    @pytest.mark.asyncio
    async def test_workflow_uses_agentic_stream(self, mock_dependencies):
        """Workflow invocations (use_tools=True) MUST use agentic streaming
        for function-calling providers.
        """
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            with patch.object(app, "_do_simple_stream", return_value="Done") as mock_simple, \
                 patch.object(app, "_do_agentic_stream", return_value="Done") as mock_agentic, \
                 patch.object(app, "_write_assistant_start"), \
                 patch.object(app, "_write_final_answer"):

                # Submit with use_tools=True (workflow/role path)
                app._do_stream("system prompt", "run preflight", use_tools=True)
                await pilot.pause()

                # Agentic stream must be called for workflows
                mock_agentic.assert_called_once()
                mock_simple.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_fc_provider_always_uses_simple(self, mock_dependencies):
        """Non-function-calling providers always use simple streaming,
        even when use_tools=True.
        """
        from agent.tui.app import ConsoleApp

        mock_dependencies["ai"]["provider"] = "gh"  # GH doesn't support FC

        app = ConsoleApp(provider="gh")
        async with app.run_test(size=(120, 40)) as pilot:
            with patch.object(app, "_do_simple_stream", return_value="Done") as mock_simple, \
                 patch.object(app, "_do_agentic_stream", return_value="Done") as mock_agentic, \
                 patch.object(app, "_write_assistant_start"), \
                 patch.object(app, "_write_final_answer"), \
                 patch("agent.core.ai.ai_service") as mock_ai:

                mock_ai.provider = "gh"

                app._do_stream("system prompt", "anything", use_tools=True)
                await pilot.pause()

                # GH falls back to simple even with use_tools=True
                mock_simple.assert_called_once()
                mock_agentic.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_response_passes_use_tools_flag(self, mock_dependencies):
        """_stream_response must forward use_tools to _do_stream."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            with patch.object(app, "_do_stream") as mock_do_stream:
                # Default call (chat) — use_tools=False
                await app._stream_response("sys", "hello")
                mock_do_stream.assert_called_with("sys", "hello", False)

                mock_do_stream.reset_mock()

                # Workflow call — use_tools=True
                await app._stream_response("sys", "run preflight", use_tools=True)
                mock_do_stream.assert_called_with("sys", "run preflight", True)

    @pytest.mark.asyncio
    async def test_use_tools_stored_for_retry(self, mock_dependencies):
        """_stream_response must save use_tools for disconnect retry."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            with patch.object(app, "_do_stream"):
                await app._stream_response("sys", "hello", use_tools=False)
                assert app._last_use_tools is False

                await app._stream_response("sys", "run preflight", use_tools=True)
                assert app._last_use_tools is True


class TestCommandHistory:
    """Verify ↑/↓ command history in the input box."""

    @pytest.mark.asyncio
    async def test_history_populated_on_submit(self, mock_dependencies):
        """Submitted input should be added to command history."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            with patch.object(app, "_stream_response", new_callable=lambda: MagicMock(return_value=None)):
                # Type and submit a command
                await pilot.press(*list("/help"), "enter")
                await pilot.pause()

                assert "/help" in app._command_history

    @pytest.mark.asyncio
    async def test_duplicate_commands_not_doubled(self, mock_dependencies):
        """Same command submitted twice should only appear once at the end."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            # Submit /help twice
            await pilot.press(*list("/help"), "enter")
            await pilot.pause()
            await pilot.press(*list("/help"), "enter")
            await pilot.pause()

            # Should NOT have duplicate consecutive entries
            assert app._command_history[-1] == "/help"
            count = sum(1 for h in app._command_history if h == "/help")
            # At most 1 consecutive duplicate
            assert count <= 1 or app._command_history[-2] != "/help"


class TestSearchCommand:
    """Verify /search command registers in BUILTIN_COMMANDS."""

    def test_search_in_builtin_commands(self):
        from agent.tui.commands import BUILTIN_COMMANDS
        assert "search" in BUILTIN_COMMANDS

    def test_tools_in_builtin_commands(self):
        from agent.tui.commands import BUILTIN_COMMANDS
        assert "tools" in BUILTIN_COMMANDS

    def test_search_in_help_text(self):
        from agent.tui.commands import format_help_text
        help_text = format_help_text({}, {})
        assert "/search" in help_text
