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
    # Mock config paths
    with patch("agent.core.config.config.runbooks_dir", tmp_path / "runbooks"), \
         patch("agent.core.config.config.agent_dir", tmp_path / ".agent"), \
         patch("agent.core.config.config.stories_dir", tmp_path / "stories"), \
         patch("agent.core.utils.load_governance_context", return_value="Rules"):
        
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
