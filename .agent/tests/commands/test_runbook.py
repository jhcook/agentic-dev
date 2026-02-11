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

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.runbook import new_runbook

runner = CliRunner()

@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(new_runbook)
    return test_app

@pytest.fixture
def mock_fs(tmp_path):
    # Create template directory with runbook template
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "runbook-template.md").write_text("# Runbook Template\n## Plan\n<plan>")

    # Mock config paths
    with patch("agent.core.config.config.runbooks_dir", tmp_path / "runbooks"), \
         patch("agent.core.config.config.agent_dir", tmp_path / ".agent"), \
         patch("agent.core.config.config.stories_dir", tmp_path / "stories"), \
         patch("agent.core.config.config.templates_dir", templates_dir), \
         patch("agent.core.context.context_loader.load_context", return_value={"rules": "Rules", "agents": {"description": "", "checks": ""}, "instructions": "", "adrs": ""}), \
         patch("agent.core.auth.decorators.validate_credentials"):
        
        (tmp_path / "runbooks").mkdir()
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "workflows").mkdir()
        (tmp_path / "stories" / "INFRA").mkdir(parents=True)
        
        yield tmp_path

def test_new_runbook_success(mock_fs, app):
    # Setup Committed Story
    story_id = "INFRA-001"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    # Mock AI
    with patch("agent.core.ai.ai_service.complete", return_value="Status: PROPOSED\n# Runbook Content"), \
         patch("agent.commands.runbook.upsert_artifact"): # Mock DB sync
         
        result = runner.invoke(app, [story_id])
        
        assert result.exit_code == 0
        assert "Runbook generated" in result.stdout
        assert (mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md").exists()

def test_new_runbook_not_committed(mock_fs, app):
    # Setup Draft Story
    story_id = "INFRA-002"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nOPEN\n# Story Content")
    
    result = runner.invoke(app, [story_id])
    
    assert result.exit_code == 1
    assert "is not COMMITTED" in result.stdout

def test_new_runbook_with_provider(mock_fs, app):
    story_id = "INFRA-003"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    with patch("agent.core.ai.ai_service.set_provider") as mock_set_provider, \
         patch("agent.core.ai.ai_service.complete", return_value="Status: PROPOSED\n# Content"), \
         patch("agent.commands.runbook.upsert_artifact"):
        
        result = runner.invoke(app, [story_id, "--provider", "openai"])
        
        assert result.exit_code == 0
        mock_set_provider.assert_called_once_with("openai")
