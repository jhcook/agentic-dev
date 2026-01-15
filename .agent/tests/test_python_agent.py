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

import os

# Adjust path to import agent modules
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agent.core.config import config
from agent.main import app

runner = CliRunner()

def test_app_version():
    # If using Typer's version flag, it should exit(0). 
    # If result.exit_code is 2, it might be "Missing command" if invoke_without_command is not set?
    # But --version raises Exit which short-circuits.
    with patch("subprocess.check_output", side_effect=Exception("No git")):
        result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, f"Output: {result.stdout}"
    assert "Agent CLI v0.1.0" in result.stdout

def test_new_story_help():
    result = runner.invoke(app, ["new-story", "--help"])
    assert result.exit_code == 0
    assert "Create a new story file" in result.stdout

@patch("agent.commands.story.get_next_id")
@patch("pathlib.Path.write_text")
@patch("pathlib.Path.mkdir")
def test_new_story_creation_auto_id(mock_mkdir, mock_write, mock_get_id):
    # Mock config to point to a temp dir (though we are mocking write/mkdir)
    # Mock user input for interactive prompts if needed?
    # CLI args: agent new-story INFRA-999
    
    # We'll test with explicit ID to avoid prompts
    with patch("pathlib.Path.exists", return_value=False):
        result = runner.invoke(app, ["new-story", "INFRA-999"], input="My Story Title\n")
    
    # Debugging
    if result.exit_code != 0:
        print(result.output)
        print(result.exc_info)

    assert result.exit_code == 0
    assert "Created story" in result.stdout
    assert "INFRA-999" in str(mock_write.call_args)

def test_new_plan_command():
    with patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.write_text") as mock_write, \
         patch("pathlib.Path.mkdir"):
        
        result = runner.invoke(app, ["new-plan", "WEB-001"], input="Plan Title\n")
        assert result.exit_code == 0
        assert "Created Plan" in result.stdout

def test_new_adr_command():
    with patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.write_text") as mock_write, \
         patch("pathlib.Path.mkdir"), \
         patch("agent.commands.adr.get_next_id", return_value="ADR-005"):
        
        result = runner.invoke(app, ["new-adr", "ADR-005"], input="ADR Title\n")
        assert result.exit_code == 0
        assert "Created ADR" in result.stdout

def test_list_stories_command():
    # Mock config.stories_dir attribute on the singleton config object
    mock_path = MagicMock()
    mock_path.rglob.return_value = [Path("/path/to/INFRA-001-test.md")]
    
    # We also need to mock Path.read_text for the yielded file
    # Only applicable if we use real Path objects in regex, but we mocked rglob to return a Path-like.
    # But here we returned a real Path object "/path/to...". Reading it will fail in real FS.
    # Better to return a MagicMock that acts like a Path.
    mock_file = MagicMock()
    mock_file.read_text.return_value = "## State\nACCEPTED\n\n# INFRA-001: Test Story"
    # Mock open() context manager
    mock_open = MagicMock()
    mock_open.__enter__.return_value.readline.return_value = "# INFRA-001: Test Story"
    mock_file.open.return_value = mock_open
    
    mock_file.name = "INFRA-001-test.md"
    mock_file.relative_to.return_value = "INFRA-001-test.md"
    mock_path.rglob.return_value = [mock_file]

    with patch.object(config, "stories_dir", mock_path):
        result = runner.invoke(app, ["list-stories"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exc_info)
        assert result.exit_code == 0
        assert "INFRA-001" in result.stdout
        assert "ACCEPTED" in result.stdout

def test_validate_story_fail_missing():
    # Mock story finding
    mock_path = MagicMock()
    mock_file = MagicMock()
    mock_file.name = "INFRA-001.md"
    mock_file.read_text.return_value = "# INFRA-001: Bad Story" # Missing sections
    mock_path.rglob.return_value = [mock_file]
    
    with patch.object(config, "stories_dir", mock_path):
        result = runner.invoke(app, ["validate-story", "INFRA-001"])
        assert result.exit_code == 1
        assert "Story schema validation failed" in result.stdout

@patch("subprocess.run")
@patch("subprocess.check_output")
@patch("agent.core.utils.get_current_branch", return_value="INFRA-005-python-rewrite")
def test_pr_workflow_inferred(mock_branch, mock_check_output, mock_run):
    # Mock git log
    mock_check_output.return_value = b"feat: rewrite agent"
    
    # Mock preflight check to pass (we can mock the function call directly or allow it to run logic)
    # Since preflight calls subprocess git diff, let's mock that output too for preflight
    mock_run.return_value = MagicMock(stdout="some_file.py", returncode=0)
    
    # We also need to mock validate_story inside preflight or it will fail
    with patch("agent.commands.check.validate_story") as mock_validate:
        result = runner.invoke(app, ["pr"])
        
    assert result.exit_code == 0
    assert "Inferred story ID from branch: INFRA-005" in result.stdout
    assert "Creating Pull Request" in result.stdout
    # Verify gh command
    args, _ = mock_run.call_args
    assert args[0][0:3] == ["gh", "pr", "create"]
    assert "main" in args[0] # base branch

@patch("subprocess.run")
def test_commit_command(mock_run):
    # commit requires story ID if branch inference fails (let's assume it fails here)
    with patch("agent.commands.workflow.infer_story_id", return_value=None):
        result = runner.invoke(app, ["commit"], input="Commit message\n")
        assert result.exit_code == 1
        assert "Story ID is required" in result.stdout

    # commit with explicit args
    result = runner.invoke(app, ["commit", "--story", "INFRA-100"], input="Fix bug\n")
    assert result.exit_code == 0
    assert "[INFRA-100] Fix bug" in str(mock_run.call_args)

@patch("subprocess.run")
@patch("agent.core.utils.get_current_branch", return_value="INFRA-005-python-rewrite")
def test_preflight_inference(mock_branch, mock_run):
    # Mock preflight checks passing (subprocess calls)
    mock_run.return_value = MagicMock(stdout="file.py", returncode=0)
    
    # Needs to mock validate_story to pass
    with patch("agent.commands.check.validate_story") as mock_validate:
        result = runner.invoke(app, ["preflight"])
        
    assert result.exit_code == 0
    assert "Inferred story ID from branch: INFRA-005" in result.stdout
    assert "preflight checks for INFRA-005" in result.stdout

def test_main_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Governed workflow CLI" in result.stdout

def test_preflight_help():
    result = runner.invoke(app, ["preflight", "--help"])
    assert result.exit_code == 0
    # Typer updated formatting, check for key phrases instead of exact lines if needed
    assert "Run preflight checks" in result.stdout or "Run governance preflight checks" in result.stdout

def test_no_args_does_not_crash():
    # Verify that invoking the app with no arguments does not crash.
    # It should exit with 0 because invoke_without_command=True.
    result = runner.invoke(app, [])
    assert result.exit_code == 0
