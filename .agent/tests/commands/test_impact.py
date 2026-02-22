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

"""Tests for agent impact command.

The ``impact`` function is registered on the main typer app via
``app.command()(with_creds(check.impact))``.  Because of lazy imports
inside the function body (DependencyAnalyzer, journey_index helpers),
we patch at the source module paths rather than on ``check``.
"""

from unittest.mock import MagicMock, patch
from pathlib import Path

import typer
from typer.testing import CliRunner
from agent.commands.check import impact


runner = CliRunner()

# Wrap the bare function in a Typer app so CliRunner can invoke it.
_app = typer.Typer()
_app.command()(impact)


def _make_story(tmp_path, content=None):
    """Create a temp story file and return (story_path, stories_dir)."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    story = stories_dir / "TEST-001-test.md"
    story.write_text(
        content
        or (
            "# TEST-001\n\n## State\n\nIN_PROGRESS\n\n"
            "## Impact Analysis Summary\n\nComponents touched: TBD\n"
        )
    )
    return story, stories_dir


# ---------------------------------------------------------------------------
# Patches needed for every test that gets past the "no files" early-return:
#   1. agent.core.dependency_analyzer.DependencyAnalyzer  (lazy import)
#   2. agent.db.journey_index.get_affected_journeys       (lazy import)
#   3. agent.db.journey_index.is_stale                    (lazy import)
#   4. agent.db.init.get_db_path                          (lazy import)
# ---------------------------------------------------------------------------

_JOURNEY_PATCHES = {
    "agent.db.journey_index.get_affected_journeys": [],
    "agent.db.journey_index.is_stale": False,
    "agent.db.init.get_db_path": "/tmp/test.db",
}


class TestImpactNoChanges:
    """No staged changes → warn and exit 0."""

    @patch("agent.commands.check.subprocess.run")
    @patch("agent.commands.check.config")
    def test_no_staged_changes(self, mock_config, mock_run, tmp_path):
        _, stories_dir = _make_story(tmp_path)
        mock_config.stories_dir = stories_dir

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = runner.invoke(_app, ["TEST-001"])
        assert result.exit_code == 0
        assert "No files to analyze" in result.output


class TestImpactBaseBranch:
    """--base flag should use git diff base...HEAD."""

    @patch("agent.commands.check.subprocess.run")
    @patch("agent.commands.check.config")
    def test_base_uses_correct_diff(self, mock_config, mock_run, tmp_path):
        _, stories_dir = _make_story(tmp_path)
        mock_config.stories_dir = stories_dir

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = runner.invoke(_app, ["TEST-001", "--base", "develop"])

        first_call = mock_run.call_args_list[0][0][0]
        assert "develop...HEAD" in first_call


class TestImpactStaticAnalysis:
    """Static analysis with mocked DependencyAnalyzer."""

    @patch("agent.commands.check.config")
    @patch("agent.commands.check.subprocess.run")
    def test_structured_output(self, mock_run, mock_config, tmp_path):
        _, stories_dir = _make_story(tmp_path)
        mock_config.stories_dir = stories_dir
        mock_config.repo_root = tmp_path
        mock_config.journeys_dir = tmp_path / "journeys"
        mock_config.journeys_dir.mkdir(parents=True)

        mock_run.return_value = MagicMock(
            stdout="backend/api.py\nbackend/models.py\n",
            returncode=0,
        )

        mock_analyzer = MagicMock()
        mock_analyzer.find_reverse_dependencies.return_value = {
            Path("backend/api.py"): {Path("backend/tests/test_api.py")},
            Path("backend/models.py"): set(),
        }

        with (
            patch(
                "agent.core.dependency_analyzer.DependencyAnalyzer",
                return_value=mock_analyzer,
            ),
            patch("agent.db.journey_index.get_affected_journeys", return_value=[]),
            patch("agent.db.journey_index.is_stale", return_value=False),
            patch("agent.db.init.get_db_path", return_value=":memory:"),
        ):
            result = runner.invoke(_app, ["TEST-001", "--base", "main", "--offline"])

        assert result.exit_code == 0
        assert "Impact Analysis" in result.output


class TestImpactUpdateStory:
    """--update-story modifies the story file."""

    @patch("agent.commands.check.config")
    @patch("agent.commands.check.subprocess.run")
    def test_update_story(self, mock_run, mock_config, tmp_path):
        story, stories_dir = _make_story(
            tmp_path,
            "# TEST-001\n\n## State\n\nIN_PROGRESS\n\n"
            "## Impact Analysis Summary\n\nComponents touched: TBD\n\n"
            "## Test Strategy\n\nUnit tests.\n",
        )
        mock_config.stories_dir = stories_dir
        mock_config.repo_root = tmp_path
        mock_config.journeys_dir = tmp_path / "journeys"
        mock_config.journeys_dir.mkdir(parents=True)

        mock_run.return_value = MagicMock(
            stdout="backend/api.py\n",
            returncode=0,
        )

        mock_analyzer = MagicMock()
        mock_analyzer.find_reverse_dependencies.return_value = {
            Path("backend/api.py"): set(),
        }

        with (
            patch(
                "agent.core.dependency_analyzer.DependencyAnalyzer",
                return_value=mock_analyzer,
            ),
            patch("agent.db.journey_index.get_affected_journeys", return_value=[]),
            patch("agent.db.journey_index.is_stale", return_value=False),
            patch("agent.db.init.get_db_path", return_value=":memory:"),
        ):
            result = runner.invoke(
                _app,
                ["TEST-001", "--base", "main", "--update-story", "--offline"],
            )

        assert result.exit_code == 0
        updated = story.read_text()
        assert "Components" in updated


class TestImpactJsonOutput:
    """--json produces valid JSON."""

    @patch("agent.commands.check.config")
    @patch("agent.commands.check.subprocess.run")
    def test_json_output(self, mock_run, mock_config, tmp_path):
        import json

        _, stories_dir = _make_story(tmp_path)
        mock_config.stories_dir = stories_dir
        mock_config.repo_root = tmp_path
        mock_config.journeys_dir = tmp_path / "journeys"
        mock_config.journeys_dir.mkdir(parents=True)

        mock_run.return_value = MagicMock(
            stdout="backend/api.py\n",
            returncode=0,
        )

        mock_analyzer = MagicMock()
        mock_analyzer.find_reverse_dependencies.return_value = {
            Path("backend/api.py"): set(),
        }

        with (
            patch(
                "agent.core.dependency_analyzer.DependencyAnalyzer",
                return_value=mock_analyzer,
            ),
            patch("agent.db.journey_index.get_affected_journeys", return_value=[]),
            patch("agent.db.journey_index.is_stale", return_value=False),
            patch("agent.db.init.get_db_path", return_value=":memory:"),
        ):
            result = runner.invoke(
                _app,
                ["TEST-001", "--base", "main", "--json", "--offline"],
            )

        assert result.exit_code == 0
        # Find JSON object in output
        output = result.output
        json_start = output.find("{")
        assert json_start >= 0, f"No JSON found in output: {output}"
        parsed = json.loads(output[json_start:])
        assert parsed["story_id"] == "TEST-001"
        assert "changed_files" in parsed
