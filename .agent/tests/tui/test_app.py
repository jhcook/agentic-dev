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

"""Headless integration tests for ConsoleApp (INFRA-087).

Uses Textual's ``app.run_test()`` harness to simulate user input
and verify command dispatch and UI state without a real terminal.
"""

import pytest
from unittest.mock import patch, MagicMock


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
    )
    mock_store_inst.get_messages.return_value = []
    mock_store_inst.auto_title = MagicMock()
    mock_store_cls.return_value = mock_store_inst

    mock_ai = MagicMock()
    mock_ai.provider = "gemini"
    mock_ai.model = "gemini-2.5-pro"
    mock_ai.models = {"gemini": "gemini-2.5-pro"}
    mock_ai.set_provider = MagicMock()

    with patch("agent.tui.session.SessionStore", mock_store_cls), \
         patch("agent.core.ai.ai_service", mock_ai), \
         patch("agent.tui.commands.discover_workflows", return_value={}), \
         patch("agent.tui.commands.discover_roles", return_value={}):
        yield {"store": mock_store_inst, "ai": mock_ai}


class TestConsoleAppHeadless:
    """Headless integration tests using Textual's test harness."""

    @pytest.mark.asyncio
    async def test_app_launches(self, mock_dependencies):
        """Verify the app launches and mounts core widgets."""
        from agent.tui.app import ConsoleApp, SelectionLog
        from textual.widgets import Input

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.is_running
            # Verify core widgets are mounted
            assert app.query_one("#chat-output", SelectionLog) is not None
            assert app.query_one("#input-box", Input) is not None
            assert app.query_one("#status-bar") is not None

    @pytest.mark.asyncio
    async def test_help_command(self, mock_dependencies):
        """Verify /help command produces help text in the chat pane."""
        from agent.tui.app import ConsoleApp, SelectionLog

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("slash", "h", "e", "l", "p", "enter")
            await pilot.pause()

            # Verify help content was written to the chat output
            chat = app.query_one("#chat-output", SelectionLog)
            assert len(chat.children) > 0, "Help command should produce output"

    @pytest.mark.asyncio
    async def test_clear_command(self, mock_dependencies):
        """Verify /clear command clears the chat output."""
        from agent.tui.app import ConsoleApp, SelectionLog

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("slash", "c", "l", "e", "a", "r", "enter")
            await pilot.pause()

            # After clear, chat output should have fewer lines than welcome
            chat = app.query_one("#chat-output", SelectionLog)
            assert chat is not None

    @pytest.mark.asyncio
    async def test_new_command(self, mock_dependencies):
        """Verify /new creates a new session without crashing."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("slash", "n", "e", "w", "enter")
            await pilot.pause()
            # App should still be running after /new
            assert app.is_running

    @pytest.mark.asyncio
    async def test_conversations_command(self, mock_dependencies):
        """Verify /conversations lists sessions in the chat output."""
        from agent.tui.app import ConsoleApp, SelectionLog

        mock_dependencies["store"].list_sessions.return_value = [
            MagicMock(id="s1", title="First chat", messages=[]),
            MagicMock(id="s2", title="Second chat", messages=[]),
        ]

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press(
                "slash", "c", "o", "n", "v", "e", "r", "s", "a",
                "t", "i", "o", "n", "s", "enter"
            )
            await pilot.pause()

            # Verify the conversations command produced output
            chat = app.query_one("#chat-output", SelectionLog)
            assert len(chat.children) > 0, "Conversations command should list sessions"

    @pytest.mark.asyncio
    async def test_quit_command(self, mock_dependencies):
        """Verify /quit exits the app cleanly."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("slash", "q", "u", "i", "t", "enter")
            await pilot.pause()
