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

from agent.commands.adr import new_adr
from agent.commands.check import validate_story
from agent.commands.plan import new_plan

# Import functions directly to compose test app for isolation
from agent.commands.story import new_story
from agent.commands.workflow import pr

runner = CliRunner()

@pytest.fixture
def app():
    """Create a test app with all target commands registered."""
    test_app = typer.Typer()
    test_app.command(name="new-story")(new_story)
    test_app.command(name="new-plan")(new_plan)
    test_app.command(name="new-adr")(new_adr)
    test_app.command(name="validate-story")(validate_story)
    test_app.command(name="pr")(pr)
    return test_app

@pytest.fixture
def mock_fs(tmp_path):
    """Setup mock file system structure."""
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "stories" / "INFRA").mkdir(parents=True)
    (agent_dir / "plans" / "INFRA").mkdir(parents=True)
    (agent_dir / "adrs").mkdir()
    (agent_dir / "templates").mkdir()
    
    # Mock Config
    with patch("agent.core.config.config.agent_dir", agent_dir), \
         patch("agent.core.config.config.stories_dir", agent_dir / "stories"), \
         patch("agent.core.config.config.plans_dir", agent_dir / "plans"), \
         patch("agent.core.config.config.adrs_dir", agent_dir / "adrs"), \
         patch("agent.core.config.config.templates_dir", agent_dir / "templates"), \
         patch("agent.core.utils.console.print"): # Silence console
        yield agent_dir

def test_new_story_interactive(app, mock_fs):
    """Test new-story with interactive prompts."""
    # Mock Prompt.ask and IntPrompt.ask
    with patch("agent.commands.story.IntPrompt.ask", return_value=1), \
         patch("agent.commands.story.Prompt.ask", return_value="My New Story"), \
         patch("agent.commands.story.typer.edit", return_value="My New Story content"):
        
        result = runner.invoke(app, ["new-story", "--offline"])
        
        assert result.exit_code == 0
        # Check file exists
        files = list((mock_fs / "stories" / "INFRA").glob("*.md"))
        assert len(files) == 1
        assert "My New Story" in files[0].read_text()

def test_new_plan_manual(app, mock_fs):
    """Test new-plan manual creation."""
    with patch("agent.commands.plan.IntPrompt.ask", return_value=1), \
         patch("agent.commands.plan.Prompt.ask", return_value="My Plan"), \
         patch("agent.commands.plan.typer.edit", return_value="My Plan content"):
        
        result = runner.invoke(app, ["new-plan", "--offline"])
        
        assert result.exit_code == 0
        files = list((mock_fs / "plans" / "INFRA").glob("*.md"))
        assert len(files) == 1
        assert "My Plan" in files[0].read_text()

def test_new_adr(app, mock_fs):
    """Test new-adr creation."""
    with patch("agent.commands.adr.Prompt.ask", return_value="Use Python"):
        
        result = runner.invoke(app, ["new-adr"])
        
        assert result.exit_code == 0
        files = list((mock_fs / "adrs").glob("*.md"))
        assert len(files) == 1
        assert "Use Python" in files[0].read_text()

def test_validate_story_valid(app, mock_fs):
    """Test validate-story with a valid file."""
    story_id = "INFRA-001"
    content = """
## Problem Statement
...
## User Story
...
## Acceptance Criteria
...
## Non-Functional Requirements
...
## Impact Analysis Summary
...
## Test Strategy
...
## Rollback Plan
...
"""
    (mock_fs / "stories" / "INFRA" / f"{story_id}.md").write_text(content)
    
    result = runner.invoke(app, ["validate-story", story_id])
    assert result.exit_code == 0
    assert "passed" in result.stdout

def test_validate_story_invalid(app, mock_fs):
    """Test validate-story with missing sections."""
    story_id = "INFRA-002"
    (mock_fs / "stories" / "INFRA" / f"{story_id}.md").write_text("# Just a title")
    
    result = runner.invoke(app, ["validate-story", story_id])
    assert result.exit_code == 1
    assert "failed" in result.stdout

@patch("agent.commands.workflow.subprocess.run")
@patch("agent.commands.workflow.subprocess.check_output")
@patch("agent.commands.workflow.preflight") # Mock preflight to avoid running it
def test_pr_command(mock_preflight, mock_check_output, mock_run, app, mock_fs):
    """Test pr command with mocked gh CLI."""
    # Setup git log and diff returns
    def check_output_side_effect(cmd, **kwargs):
        if "log" in cmd:
            return b"feat: New feature"
        return "some diff"
    mock_check_output.side_effect = check_output_side_effect
    
    with patch("agent.commands.workflow.validate_credentials"), \
         patch("agent.commands.workflow.typer.edit", return_value="Manual PR Summary"), \
         patch("agent.core.ai.ai_service.complete", return_value="AI PR Summary"):
        # Run PR
        result = runner.invoke(app, ["pr", "--story", "INFRA-123", "--web"])
    
    assert result.exit_code == 0
    
    # Update assertions to match actual calls
    # Check that subprocess.run was called with gh command
    # gh pr create --title ... --body ... --base main --web
    
    args, _ = mock_run.call_args
    cmd_list = args[0]
    assert cmd_list[0] == "gh"
    assert cmd_list[1] == "pr"
    assert cmd_list[2] == "create"
    assert "--web" in cmd_list
    assert "[INFRA-123] feat: New feature" in cmd_list # Title check

@patch("agent.commands.workflow.subprocess.run")
@patch("agent.commands.workflow.subprocess.check_output")
@patch("agent.commands.workflow.preflight")
def test_pr_command_with_provider(mock_preflight, mock_check_output, mock_run, app, mock_fs):
    """Test pr command with --provider flag."""
    def check_output_side_effect(cmd, **kwargs):
        if "log" in cmd:
            return b"feat: New feature"
        return "some diff"
    mock_check_output.side_effect = check_output_side_effect
    
    with patch("agent.commands.workflow.validate_credentials"), \
         patch("agent.commands.workflow.typer.edit", return_value="Manual PR Summary"), \
         patch("agent.core.ai.ai_service.complete", return_value="AI PR Summary"):
        result = runner.invoke(app, ["pr", "--story", "INFRA-123", "--provider", "openai"])
    
    assert result.exit_code == 0
    # Check preflight was called with provider
    args, kwargs = mock_preflight.call_args
    assert kwargs['provider'] == "openai"
