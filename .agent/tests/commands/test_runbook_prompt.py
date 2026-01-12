import pytest
from typer.testing import CliRunner
from agent.main import app
from unittest.mock import patch, MagicMock

runner = CliRunner()

@pytest.fixture
def mock_deps(tmp_path):
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "stories" / "INFRA").mkdir(parents=True)
    (agent_dir / "runbooks").mkdir()
    (agent_dir / "rules").mkdir()
    
    # Create agents.yaml
    (agent_dir / "agents.yaml").write_text("""
team:
  - role: architect
    name: "Architect Bot"
    description: "Design checks"
    governance_checks:
      - "Check ADRs"
  - role: security
    name: "Sec Bot"
    description: "Security checks"
    governance_checks:
      - "Check PII"
""")
    
    story_file = agent_dir / "stories" / "INFRA" / "STORY-PROMPT.md"
    story_file.write_text("# Story for Prompt Test")
    
    return {"root": tmp_path, "story": story_file}


@patch("agent.core.ai.ai_service.complete")
@patch("agent.core.config.config.agent_dir")
def test_runbook_prompt_construction(mock_agent_dir, mock_complete, mock_deps):
    mock_agent_dir.return_value = mock_deps["root"] / ".agent"
    
    # Mock yaml module
    mock_yaml = MagicMock()
    # Return a dict structure matching the agents.yaml content
    mock_yaml.safe_load.return_value = {
        "team": [
            {
                "role": "architect",
                "name": "Architect Bot",
                "description": "Design checks",
                "governance_checks": ["Check ADRs"]
            },
            {
                "role": "security",
                "name": "Sec Bot",
                "description": "Security checks",
                "governance_checks": ["Check PII"]
            }
        ]
    }
    

    import sys
    with patch.dict(sys.modules, {"yaml": mock_yaml}):
        with patch("agent.core.config.config.runbooks_dir", mock_deps["root"] / ".agent" / "runbooks"), \
             patch("agent.core.config.config.stories_dir", mock_deps["root"] / ".agent" / "stories"), \
             patch("agent.core.config.config.rules_dir", mock_deps["root"] / ".agent" / "rules"):
             
            mock_complete.return_value = "Runbook Content"
             
            result = runner.invoke(app, ["new-runbook", "STORY-PROMPT"])
         
            assert result.exit_code == 0
         
            # Capture the arguments passed to complete
            args, _ = mock_complete.call_args
            system_prompt = args[0]
         
            # Verification 1: Check dynamic agents are present
            assert "Architect Bot" in system_prompt
            assert "Sec Bot" in system_prompt
            assert "Check ADRs" in system_prompt
         
            # Verification 2: Check Definition of Done
            assert "## Definition of Done" in system_prompt
            assert "CHANGELOG.md updated" in system_prompt
            assert "Logs are structured and free of PII" in system_prompt
