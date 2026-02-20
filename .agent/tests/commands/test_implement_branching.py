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

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.implement import (
    create_branch,
    get_current_branch,
    implement,
    is_git_dirty,
    sanitize_branch_name,
)

runner = CliRunner()

@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(implement)
    return test_app

# Helper Tests

def test_sanitize_branch_name():
    assert sanitize_branch_name("My Feature Title") == "my-feature-title"
    assert sanitize_branch_name("Fix: Bug #123") == "fix-bug-123"
    assert sanitize_branch_name("  Trim Me  ") == "trim-me"
    assert sanitize_branch_name("User's Input!") == "user-s-input"

def test_get_current_branch():
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"feature/branch\n"
        assert get_current_branch() == "feature/branch"

def test_get_current_branch_error():
    with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git")):
        assert get_current_branch() == ""

def test_is_git_dirty_clean():
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"" # No output from status --porcelain
        assert is_git_dirty() is False

def test_is_git_dirty_dirty():
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b" M somefile.py"
        assert is_git_dirty() is True

def test_create_branch_new():
    with patch("subprocess.run") as mock_run:
        # First call fails (check existence), second succeeds (create)
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "git"), # git rev-parse (not found)
            MagicMock(returncode=0) # git checkout -b
        ]
        
        create_branch("INFRA-123", "my-title")
        
        # Verify calls
        assert mock_run.call_count == 2
        # Check checkout -b call
        call_args = mock_run.call_args_list[1]
        cmd = call_args[0][0]
        assert "git" in cmd
        assert "checkout" in cmd
        assert "-b" in cmd
        assert "INFRA-123/my-title" in cmd

def test_create_branch_existing():
    with patch("subprocess.run") as mock_run:
        # First call succeeds (branch exists), second succeeds (checkout)
        mock_run.side_effect = [
             MagicMock(returncode=0), # git rev-parse (found)
             MagicMock(returncode=0)  # git checkout (no -b)
        ]
        
        create_branch("INFRA-123", "my-title")
        
        # Verify calls
        assert mock_run.call_count == 2
        
        # Check checkout call (NO -b)
        call_args = mock_run.call_args_list[1]
        cmd = call_args[0][0]
        assert "git" in cmd
        assert "checkout" in cmd
        assert "-b" not in cmd
        assert "INFRA-123/my-title" in cmd


# Command Flow Tests

@pytest.fixture
def mock_deps(tmp_path):
    with patch("agent.commands.implement.get_current_branch") as mock_branch, \
         patch("agent.commands.implement.is_git_dirty") as mock_dirty, \
         patch("agent.commands.implement.create_branch") as mock_create, \
         patch("agent.core.utils.find_story_file") as mock_find_story, \
         patch("agent.commands.implement.find_runbook_file") as mock_find_runbook, \
         patch("agent.core.context.context_loader.load_context", return_value={"rules": "Rules", "agents": {}, "instructions": "", "adrs": ""}), \
         patch("agent.commands.implement.update_story_state"), \
         patch("agent.core.auth.decorators.validate_credentials"), \
         patch("agent.core.ai.ai_service.complete", return_value="Plan"):
        
        # Setup runbook
        rb_path = tmp_path / "INFRA-055-runbook.md"
        rb_path.write_text("Status: ACCEPTED\n# Content")
        mock_find_runbook.return_value = rb_path
        
        # Setup story
        st_path = tmp_path / "INFRA-055-story.md"
        st_path.write_text("# INFRA-055: Automate Stuff\n## State\nDRAFT")
        mock_find_story.return_value = st_path
        
        yield {
            "branch": mock_branch,
            "dirty": mock_dirty,
            "create": mock_create,
            "find_story": mock_find_story
        }

def test_implement_dirty_state_fails(app, mock_deps):
    mock_deps["dirty"].return_value = True
    mock_deps["branch"].return_value = "main"
    
    result = runner.invoke(app, ["INFRA-055"])
    
    assert result.exit_code == 1
    assert "Uncommitted changes" in result.stdout

def test_implement_wrong_branch_fails(app, mock_deps):
    mock_deps["dirty"].return_value = False
    mock_deps["branch"].return_value = "feature/some-other-thing"
    
    result = runner.invoke(app, ["INFRA-055"])
    
    assert result.exit_code == 1
    assert "You must be on 'main'" in result.stdout

def test_implement_from_main_creates_branch(app, mock_deps):
    mock_deps["dirty"].return_value = False
    mock_deps["branch"].return_value = "main"
    
    result = runner.invoke(app, ["INFRA-055"])
    
    assert result.exit_code == 0
    # Code passes the RAW title, create_branch handles sanitization
    mock_deps["create"].assert_called_once_with("INFRA-055", "Automate Stuff")

def test_implement_from_correct_branch_proceeds(app, mock_deps):
    mock_deps["dirty"].return_value = False
    mock_deps["branch"].return_value = "INFRA-055/automate-stuff"
    
    result = runner.invoke(app, ["INFRA-055"])
    
    assert result.exit_code == 0
    # Should NOT try to create branch if already on it
    mock_deps["create"].assert_not_called()
    assert "Already on valid story branch" in result.stdout

def test_implement_from_same_id_branch_proceeds(app, mock_deps):
    # Case where user manually named it slightly differently but prefix matches
    mock_deps["dirty"].return_value = False
    mock_deps["branch"].return_value = "INFRA-055/manual-name"
    
    result = runner.invoke(app, ["INFRA-055"])
    
    assert result.exit_code == 0
    mock_deps["create"].assert_not_called()
    assert "Already on valid story branch" in result.stdout
