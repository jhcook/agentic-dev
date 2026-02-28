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

"""Tests for model selector panel and --model flag (INFRA-088).

Tests the PREFERRED_MODELS list, model selection handler, and
ConsoleApp model wiring via headless Textual tests.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.tui.app import PREFERRED_MODELS


class TestPreferredModels:
    """Test the curated PREFERRED_MODELS constant."""

    def test_has_entries(self):
        assert len(PREFERRED_MODELS) > 0

    def test_entry_format(self):
        """Each entry should be (display_name, provider, model_id_or_none)."""
        for entry in PREFERRED_MODELS:
            assert len(entry) == 3
            display_name, provider, model_id = entry
            assert isinstance(display_name, str)
            assert isinstance(provider, str)
            assert model_id is None or isinstance(model_id, str)

    def test_has_gemini_models(self):
        providers = {e[1] for e in PREFERRED_MODELS}
        assert "gemini" in providers

    def test_has_openai_models(self):
        providers = {e[1] for e in PREFERRED_MODELS}
        assert "openai" in providers

    def test_has_anthropic_models(self):
        providers = {e[1] for e in PREFERRED_MODELS}
        assert "anthropic" in providers

    def test_has_vertex_models(self):
        providers = {e[1] for e in PREFERRED_MODELS}
        assert "vertex" in providers

    def test_display_names_are_unique(self):
        names = [e[0] for e in PREFERRED_MODELS]
        assert len(names) == len(set(names)), "Display names must be unique"


class TestModelSelectionHandler:
    """Test ConsoleApp._handle_model_selection logic."""

    @pytest.fixture
    def mock_dependencies(self):
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
        mock_ai.models = {"gemini": "gemini-2.5-pro", "openai": "gpt-4o"}
        mock_ai.clients = {"gemini": MagicMock(), "openai": MagicMock()}
        mock_ai.set_provider = MagicMock()
        mock_ai.is_forced = False

        with patch("agent.tui.session.SessionStore", mock_store_cls), \
             patch("agent.core.ai.ai_service", mock_ai), \
             patch("agent.tui.commands.discover_workflows", return_value={}), \
             patch("agent.tui.commands.discover_roles", return_value={}):
            yield {"store": mock_store_inst, "ai": mock_ai}

    @pytest.mark.asyncio
    async def test_model_list_populates(self, mock_dependencies):
        """Model list should contain entries for configured providers."""
        from agent.tui.app import ConsoleApp
        from textual.widgets import ListView

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            model_list = app.query_one("#model-list", ListView)
            # Should have entries for gemini and openai (both in clients)
            assert len(model_list.children) > 0

    @pytest.mark.asyncio
    async def test_model_list_filters_unconfigured(self, mock_dependencies):
        """Models for unconfigured providers should not appear."""
        from agent.tui.app import ConsoleApp
        from textual.widgets import ListView, ListItem

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            model_list = app.query_one("#model-list", ListView)
            # Anthropic is NOT in mock_ai.clients, so no anthropic models
            for child in model_list.children:
                if isinstance(child, ListItem) and child.name:
                    assert not child.name.startswith("anthropic:"), \
                        "Unconfigured provider models should not appear"

    @pytest.mark.asyncio
    async def test_model_selection_switches_provider(self, mock_dependencies):
        """Selecting a model should switch both provider and model."""
        from agent.tui.app import ConsoleApp

        ai = mock_dependencies["ai"]
        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            app._handle_model_selection("openai:gpt-4o")
            assert ai.provider == "openai"
            assert ai.models["openai"] == "gpt-4o"
            assert ai.is_forced is True

    @pytest.mark.asyncio
    async def test_unconfigured_provider_shows_error(self, mock_dependencies):
        """Selecting a model for unconfigured provider should show error."""
        from agent.tui.app import ConsoleApp

        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            # anthropic is not in clients
            app._handle_model_selection("anthropic:claude-sonnet-4-20250514")
            # provider should NOT have changed
            ai = mock_dependencies["ai"]
            assert ai.provider == "gemini"


class TestModelCLIFlag:
    """Test --model flag wiring through ConsoleApp."""

    @pytest.fixture
    def mock_dependencies(self):
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
        mock_ai.clients = {"gemini": MagicMock()}
        mock_ai.set_provider = MagicMock()

        with patch("agent.tui.session.SessionStore", mock_store_cls), \
             patch("agent.core.ai.ai_service", mock_ai), \
             patch("agent.tui.commands.discover_workflows", return_value={}), \
             patch("agent.tui.commands.discover_roles", return_value={}):
            yield {"store": mock_store_inst, "ai": mock_ai}

    @pytest.mark.asyncio
    async def test_model_override_applied(self, mock_dependencies):
        """--model flag should override the active model in ai_service."""
        from agent.tui.app import ConsoleApp

        ai = mock_dependencies["ai"]
        app = ConsoleApp(provider="gemini", model="gemini-2.5-flash")
        async with app.run_test(size=(120, 40)) as pilot:
            assert ai.models["gemini"] == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_no_model_override(self, mock_dependencies):
        """Without --model, default model should be unchanged."""
        from agent.tui.app import ConsoleApp

        ai = mock_dependencies["ai"]
        app = ConsoleApp(provider="gemini")
        async with app.run_test(size=(120, 40)) as pilot:
            assert ai.models["gemini"] == "gemini-2.5-pro"
