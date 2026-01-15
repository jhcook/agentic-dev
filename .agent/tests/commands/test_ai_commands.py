from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()


@pytest.fixture
def mock_deps(tmp_path):
    # Mock directory structure
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "stories" / "INFRA").mkdir(parents=True)
    (agent_dir / "plans").mkdir()
    (agent_dir / "runbooks").mkdir()
    (agent_dir / "rules").mkdir()
    
    # Create dummy story in subfolder for correct scoping
    story_file = agent_dir / "stories" / "INFRA" / "STORY-123-test.md"
    story_file.write_text("# Test Story\nContext here.")
    
    # Create dummy rule
    rule_file = agent_dir / "rules" / "rule1.mdc"
    rule_file.write_text("Rule 1")

    return {"root": tmp_path, "story": story_file}

@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.config.config.agent_dir") 
def test_plan_command(mock_agent_dir, mock_complete, mock_deps):
    mock_agent_dir.return_value = mock_deps["root"] / ".agent" 
    
    with patch("agent.core.config.config.stories_dir", mock_deps["root"] / ".agent" / "stories"), \
         patch("agent.core.config.config.plans_dir", mock_deps["root"] / ".agent" / "plans"), \
         patch("agent.core.config.config.rules_dir", mock_deps["root"] / ".agent" / "rules"):

        mock_complete.return_value = "# Plan Content\nSteps..."
        

        # Invoke command
        result = runner.invoke(app, ["plan", "STORY-123"])
        
        # Verify
        if result.exit_code != 0:
            print(result.stdout) # For debugging
        assert result.exit_code == 0
        assert "Plan generated" in result.stdout
        # Check file created
        plan_files = list((mock_deps["root"] / ".agent" / "plans").glob("INFRA/STORY-123-impl-plan.md"))
        assert len(plan_files) > 0
        assert plan_files[0].read_text() == "# Plan Content\nSteps..."

@patch("agent.core.ai.ai_service.complete")
def test_new_runbook_command(mock_complete, mock_deps):
    # Mock yaml module since it might not be installed in test env
    mock_yaml = MagicMock()
    mock_yaml.safe_load.return_value = {"team": []}
    
    with patch.dict("sys.modules", {"yaml": mock_yaml}):
        with patch("agent.core.config.config.runbooks_dir", mock_deps["root"] / ".agent" / "runbooks"), \
             patch("agent.core.config.config.stories_dir", mock_deps["root"] / ".agent" / "stories"), \
             patch("agent.core.config.config.rules_dir", mock_deps["root"] / ".agent" / "rules"):
             
            mock_complete.return_value = "# Runbook Content"
            
            result = runner.invoke(app, ["new-runbook", "STORY-123"])
            
            if result.exit_code != 0:
                print(result.stdout)
            assert result.exit_code == 0
            assert "Runbook generated" in result.stdout
            
            runbook_files = list((mock_deps["root"] / ".agent" / "runbooks").glob("INFRA/STORY-123-runbook.md"))
            assert len(runbook_files) > 0

@patch("agent.core.ai.ai_service.complete")
def test_match_story_command(mock_complete, mock_deps):
     with patch("agent.core.config.config.stories_dir", mock_deps["root"] / ".agent" / "stories"), \
          patch("agent.core.utils.subprocess.check_output") as mock_git:
          
        mock_git.return_value = b"file1.py\nfile2.py"
        mock_complete.return_value = "STORY-123"
        
        result = runner.invoke(app, ["match-story", "--files", "file1.py file2.py"])
        
        assert result.exit_code == 0
        assert "STORY-123" in result.stdout
