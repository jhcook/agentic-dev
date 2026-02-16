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

"""Tests for agent query command."""

from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from agent.commands.query import grep_fallback

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def runner():
    return CliRunner()


class TestQueryCommand:
    """Tests for the query command."""
    
    def test_query_help(self, runner):
        """Test that --help shows usage information."""
        from agent.main import app
        result = runner.invoke(app, ["query", "--help"])
        
        assert result.exit_code == 0
        assert "Ask a natural language question" in result.output
        assert "--offline" in result.output
    
    @patch("agent.core.ai.ai_service")
    def test_offline_mode_uses_grep(self, mock_ai_service, runner):
        """Test that --offline flag uses grep fallback."""
        mock_ai_service.provider = "gemini"  # AI is available
        
        with patch("agent.commands.query.grep_fallback") as mock_grep:
            from agent.main import app
            result = runner.invoke(app, ["query", "--offline", "test query"])
            
            mock_grep.assert_called_once_with("test query")
    
    @patch("agent.core.ai.ai_service")
    def test_no_provider_shows_warning_and_falls_back(self, mock_ai_service, runner):
        """Test that missing AI provider triggers fallback."""
        mock_ai_service.provider = None  # AI not available
        
        with patch("agent.commands.query.grep_fallback") as mock_grep:
            from agent.main import app
            result = runner.invoke(app, ["query", "test query"])
            
            assert "No AI provider configured" in result.output
            mock_grep.assert_called_once()
    
    @patch("agent.core.ai.ai_service")
    @patch("agent.commands.query.run_query")
    def test_ai_query_success(self, mock_run_query, mock_ai_service, runner):
        """Test successful AI query."""
        mock_ai_service.provider = "gemini"
        mock_run_query.return_value = "This is the answer."  # Make it sync for test
        
        # Need to mock asyncio.run since run_query is async
        with patch("agent.commands.query.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = "This is the answer."
            
            from agent.main import app
            result = runner.invoke(app, ["query", "what is this?"])
            
            assert result.exit_code == 0
            assert "Answer" in result.output


class TestGrepFallback:
    """Tests for the grep fallback function."""
    
    @patch("agent.commands.query.subprocess.run")
    @patch("agent.commands.query.Path")
    def test_grep_fallback_calls_grep(self, mock_path, mock_subprocess):
        """Test that grep fallback calls grep with correct arguments."""
        mock_path.return_value.exists.return_value = True
        
        grep_fallback("test query")
        
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "grep" in call_args
        assert "test query" in call_args
