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

"""Tests for visualize CLI command."""

import pytest
from unittest.mock import patch
from click.testing import CliRunner

from agent.commands.visualize import visualize

runner = CliRunner()


@pytest.fixture
def mock_graph_data():
    """Mock graph data for testing."""
    return {
        "nodes": [
            {"id": "STORY-001", "type": "story", "title": "Test Story", "path": "stories/STORY-001.md"},
            {"id": "RUNBOOK-001", "type": "runbook", "title": "Test Runbook", "path": "runbooks/RUNBOOK-001.md"},
        ],
        "edges": [
            {"source": "STORY-001", "target": "RUNBOOK-001"}
        ]
    }


class TestVisualizeHelp:
    """Tests for visualize command help output."""

    def test_visualize_help(self):
        """Test that --help shows available subcommands."""
        result = runner.invoke(visualize, ["--help"])
        
        assert result.exit_code == 0
        assert "graph" in result.output
        assert "flow" in result.output


class TestGraphSubcommand:
    """Tests for visualize graph subcommand."""

    @patch("agent.commands.visualize.build_from_repo")
    @patch("agent.commands.visualize.get_repo_url")
    def test_graph_outputs_mermaid(self, mock_repo_url, mock_build, mock_graph_data):
        """Test that graph subcommand outputs Mermaid syntax."""
        mock_build.return_value = mock_graph_data
        mock_repo_url.return_value = "https://github.com/test/repo/blob/main/"
        
        result = runner.invoke(visualize, ["graph"])
        
        assert result.exit_code == 0
        assert "graph TD" in result.output
        assert "STORY-001" in result.output
        assert "RUNBOOK-001" in result.output

    @patch("agent.commands.visualize.build_from_repo")
    @patch("agent.commands.visualize.get_repo_url")
    def test_graph_contains_edges(self, mock_repo_url, mock_build, mock_graph_data):
        """Test that graph output contains edge definitions."""
        mock_build.return_value = mock_graph_data
        mock_repo_url.return_value = ""
        
        result = runner.invoke(visualize, ["graph"])
        
        assert result.exit_code == 0
        assert "-->" in result.output


class TestFlowSubcommand:
    """Tests for visualize flow subcommand."""

    @patch("agent.commands.visualize.build_from_repo")
    @patch("agent.commands.visualize.get_repo_url")
    def test_flow_with_valid_story(self, mock_repo_url, mock_build, mock_graph_data):
        """Test flow subcommand with a valid story ID."""
        mock_build.return_value = mock_graph_data
        mock_repo_url.return_value = ""
        
        result = runner.invoke(visualize, ["flow", "STORY-001"])
        
        assert result.exit_code == 0
        assert "graph TD" in result.output
        assert "STORY-001" in result.output

    @patch("agent.commands.visualize.build_from_repo")
    @patch("agent.commands.visualize.get_repo_url")
    def test_flow_with_invalid_story(self, mock_repo_url, mock_build, mock_graph_data):
        """Test flow subcommand with a non-existent story ID."""
        mock_build.return_value = mock_graph_data
        mock_repo_url.return_value = ""
        
        result = runner.invoke(visualize, ["flow", "NONEXISTENT-999"])
        
        # Should exit with error (exit code 1)
        assert result.exit_code != 0

    @patch("agent.commands.visualize.build_from_repo")
    @patch("agent.commands.visualize.get_repo_url")
    def test_flow_error_message_on_invalid_story(self, mock_repo_url, mock_build, mock_graph_data):
        """Test that flow shows error message for invalid story."""
        mock_build.return_value = mock_graph_data
        mock_repo_url.return_value = ""
        
        result = runner.invoke(visualize, ["flow", "NONEXISTENT-999"])
        
        # Error message should be in output
        assert "not found" in result.output.lower()
