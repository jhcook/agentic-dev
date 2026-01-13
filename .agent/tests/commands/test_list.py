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

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typer.testing import CliRunner
from pathlib import Path
from agent.commands.list import list_stories, list_plans, list_runbooks
import typer

app = typer.Typer()
app.command(name="list-stories")(list_stories)
app.command(name="list-plans")(list_plans)
app.command(name="list-runbooks")(list_runbooks)

runner = CliRunner()

@pytest.fixture
def mock_stories(tmp_path):
    """Create some dummy story files for testing."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir(parents=True)
    
    story1 = stories_dir / "STORY-001-test.md"
    story1.write_text("# STORY-001: Test Story\n\n## State\n\nACCEPTED")
    
    story2 = stories_dir / "STORY-002-another.md"
    story2.write_text("# STORY-002: Another Story\n\n## State\n\nDRAFT")
    
    story3 = stories_dir / "STORY-003-pii.md"
    story3.write_text("# STORY-003: My email is test@example.com\n\n## State\n\nDRAFT")
    
    return stories_dir

@pytest.fixture
def mock_config(mock_stories):
    with patch("agent.commands.list.config") as mock:
        mock.stories_dir = mock_stories
        mock.repo_root = mock_stories.parent
        # Also need plans/runbooks if we test those, but let's focus on stories first for patterns
        mock.plans_dir = mock_stories.parent / "plans"
        mock.plans_dir.mkdir(exist_ok=True)
        mock.runbooks_dir = mock_stories.parent / "runbooks"
        mock.runbooks_dir.mkdir(exist_ok=True)
        yield mock

def test_list_stories_formatted_json(mock_config):
    result = runner.invoke(app, ["list-stories", "--format", "json"])
    assert result.exit_code == 0
    assert '"ID": "STORY-001"' in result.stdout
    assert '"Title": "Test Story"' in result.stdout
    assert '"State": "ACCEPTED"' in result.stdout
    # Expect JSON format (start with [)
    assert result.stdout.strip().startswith("[")

def test_list_stories_formatted_csv(mock_config):
    result = runner.invoke(app, ["list-stories", "--format", "csv"])
    assert result.exit_code == 0
    assert "ID,Title,State" in result.stdout
    assert "STORY-001,Test Story,ACCEPTED" in result.stdout

def test_list_stories_output_file(mock_config, tmp_path):
    output_file = tmp_path / "output.json"
    result = runner.invoke(app, ["list-stories", "--format", "json", "--output", str(output_file)])
    assert result.exit_code == 0
    assert output_file.exists()
    assert "STORY-001" in output_file.read_text()
    assert "✅ Output written" in result.stdout

def test_list_stories_invalid_format(mock_config):
    result = runner.invoke(app, ["list-stories", "--format", "invalid"])
    assert result.exit_code == 1
    assert "Unsupported format: invalid" in result.stdout

def test_list_stories_pretty_default(mock_config):
    result = runner.invoke(app, ["list-stories"])
    assert result.exit_code == 0
    # Rich table output contains borders etc, hard to assert exact string
    # But we check for content
    assert "STORY-001" in result.stdout
    assert "Test Story" in result.stdout

def test_list_stories_pii_scrubbing(mock_config):
    result = runner.invoke(app, ["list-stories", "--format", "json"])
    assert result.exit_code == 0
    # The email should be redacted
    assert "test@example.com" not in result.stdout
    assert "[REDACTED:EMAIL]" in result.stdout
