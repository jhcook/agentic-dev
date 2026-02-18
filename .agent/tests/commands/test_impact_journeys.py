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

"""Integration tests for impact-to-journey mapping CLI (INFRA-059)."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()


def _write_journey(
    journeys_dir: Path,
    jid: str,
    *,
    state: str = "COMMITTED",
    files: list | None = None,
    tests: list | None = None,
    title: str = "",
) -> None:
    scope_dir = journeys_dir / "INFRA"
    scope_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": jid,
        "title": title or f"Journey {jid}",
        "state": state,
        "implementation": {
            "files": files or [],
            "tests": tests or [],
        },
    }
    path = scope_dir / f"{jid}-test.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False))


@pytest.fixture
def setup_repo(tmp_path: Path, monkeypatch):
    """Set up a minimal repo with journeys and a story for impact testing."""
    # Create necessary dirs
    stories_dir = tmp_path / ".agent" / "cache" / "stories" / "INFRA"
    stories_dir.mkdir(parents=True)
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys"
    journeys_dir.mkdir(parents=True)
    cache_dir = tmp_path / ".agent" / "cache"

    # Write a minimal story file
    story = stories_dir / "TEST-001-test-story.md"
    story.write_text(
        "# TEST-001\n## State\nIN_PROGRESS\n## Impact Analysis Summary\nTBD"
    )

    # Write a journey with file patterns
    _write_journey(
        journeys_dir,
        "JRN-100",
        files=["src/agent/**/*.py"],
        tests=["tests/test_agent.py"],
        title="Agent Core",
    )

    # Mock config to use tmp_path
    from agent.core.config import config

    monkeypatch.setattr(config, "repo_root", tmp_path)
    monkeypatch.setattr(config, "stories_dir", stories_dir.parent)
    monkeypatch.setattr(config, "journeys_dir", journeys_dir)
    monkeypatch.setattr(config, "cache_dir", cache_dir)

    return tmp_path


class TestImpactJourneys:
    def test_impact_shows_affected_journeys(self, setup_repo: Path) -> None:
        """The impact command should display affected journeys in output."""
        changed = "src/agent/commands/check.py"

        with patch(
            "subprocess.run",
            return_value=type(
                "R", (), {"stdout": changed, "stderr": "", "returncode": 0}
            )(),
        ):
            result = runner.invoke(app, ["impact", "TEST-001", "--base", "HEAD~1"])

        assert result.exit_code == 0
        assert "JRN-100" in result.output or "Affected Journeys" in result.output

    def test_impact_json_output(self, setup_repo: Path) -> None:
        """--json should output machine-readable JSON with affected_journeys."""
        changed = "src/agent/commands/check.py"

        with patch(
            "subprocess.run",
            return_value=type(
                "R", (), {"stdout": changed, "stderr": "", "returncode": 0}
            )(),
        ):
            result = runner.invoke(
                app, ["impact", "TEST-001", "--base", "HEAD~1", "--json"]
            )

        assert result.exit_code == 0
        # The JSON output should contain affected_journeys
        assert "affected_journeys" in result.output

    def test_impact_no_journeys(self, setup_repo: Path) -> None:
        """Files not matching any pattern should show 'No journeys affected'."""
        changed = "README.md"

        with patch(
            "subprocess.run",
            return_value=type(
                "R", (), {"stdout": changed, "stderr": "", "returncode": 0}
            )(),
        ):
            result = runner.invoke(app, ["impact", "TEST-001", "--base", "HEAD~1"])

        assert result.exit_code == 0
        assert "No journeys affected" in result.output
