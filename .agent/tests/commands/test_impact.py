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
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import typer
from typer.testing import CliRunner
from agent.commands.impact import impact
from agent.core.check.models import ImpactResult

runner = CliRunner()
_app = typer.Typer()
_app.command()(impact)

@patch("agent.core.check.impact.run_impact_analysis")
def test_static_analysis_output(mock_run_impact):
    mock_run_impact.return_value = {
        "story_id": "TEST-001",
        "changed_files": ["backend/api.py"],
        "total_impacted": 1,
        "reverse_dependencies": {"backend/api.py": ["backend/tests/test_api.py"]},
        "affected_journeys": [],
        "test_markers": ["backend/tests/test_api.py"],
        "components": ["backend"],
        "error": None,
        "impact_summary": "Impact Analysis Summary:\n- 1 file(s) changed",
        "is_offline": True,
        "ungoverned_files": [],
        "rebuilt_journey_index": False,
        "story_updated": False,
        "story_file": "/tmp/TEST-001.md"
    }
    
    result = runner.invoke(_app, ["TEST-001", "--base", "main", "--offline"])
    
    assert result.exit_code == 0
    assert "Impact Analysis" in result.output
    # check that mock was called correctly
    mock_run_impact.assert_called_once_with(
        story_id="TEST-001",
        offline=True,
        base="main",
        update_story=False,
        provider=None,
        rebuild_index=False
    )

@patch("agent.core.check.impact.run_impact_analysis")
def test_update_story(mock_run_impact):
    mock_run_impact.return_value = {
        "story_id": "TEST-001",
        "changed_files": ["backend/api.py"],
        "total_impacted": 1,
        "reverse_dependencies": {"backend/api.py": ["backend/tests/test_api.py"]},
        "affected_journeys": [],
        "test_markers": ["backend/tests/test_api.py"],
        "components": ["backend"],
        "error": None,
        "impact_summary": "Impact Analysis Summary:\n- 1 file(s) changed",
        "is_offline": True,
        "ungoverned_files": [],
        "rebuilt_journey_index": False,
        "story_updated": True,
        "story_file": "/tmp/TEST-001.md"
    }
    
    result = runner.invoke(_app, ["TEST-001", "--base", "main", "--update-story", "--offline"])
    assert result.exit_code == 0
    assert "Updated story file" in result.output

@patch("agent.core.check.impact.run_impact_analysis")
def test_json_output(mock_run_impact):
    mock_run_impact.return_value = {
        "story_id": "TEST-001",
        "changed_files": ["backend/api.py"],
        "total_impacted": 1,
        "reverse_dependencies": {"backend/api.py": ["backend/tests/test_api.py"]},
        "affected_journeys": [],
        "test_markers": ["backend/tests/test_api.py"],
        "components": ["backend"],
        "error": None,
        "impact_summary": "Impact Analysis Summary:\n- 1 file(s) changed",
        "is_offline": True,
        "ungoverned_files": [],
        "rebuilt_journey_index": False,
        "story_updated": False,
        "story_file": "/tmp/TEST-001.md"
    }

    result = runner.invoke(_app, ["TEST-001", "--base", "main", "--json", "--offline"])
    assert result.exit_code == 0
    
    output = result.output
    json_start = output.find("{")
    assert json_start >= 0
    parsed = json.loads(output[json_start:])
    assert parsed["story_id"] == "TEST-001"
    assert "backend/api.py" in parsed["changed_files"]
