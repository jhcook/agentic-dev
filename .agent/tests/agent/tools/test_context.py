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

"""
Unit and Integration tests for the context tool domain.
"""

import pytest
import subprocess
from agent.tools.context import checkpoint, rollback

@pytest.fixture
def git_repo(tmp_path):
    """Fixture to create a temporary git repository for testing."""
    # Initialize a new git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    
    # Create an initial commit so we have a HEAD
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial state")
    subprocess.run(["git", "add", "test.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)
    
    return tmp_path

def test_checkpoint_and_rollback_integration(git_repo):
    """Verify true integration of checkpoint and rollback in a real git repo."""
    test_file = git_repo / "test.txt"
    assert test_file.read_text() == "initial state"

    # 1. Create a checkpoint
    checkpoint_result = checkpoint("integration_test", repo_root=git_repo)
    assert checkpoint_result["success"] is True

    # 2. Mutate the file
    test_file.write_text("modified state")

    # 3. Add a new untracked file
    new_file = git_repo / "new.txt"
    new_file.write_text("new content")

    # 4. Rollback to the checkpoint
    rollback_result = rollback(repo_root=git_repo)
    assert rollback_result["success"] is True

    # 5. Assert the state is completely restored
    assert test_file.read_text() == "initial state"
    assert not new_file.exists()

def test_rollback_no_checkpoint_error(git_repo):
    """Verify error when no checkpoint exists."""
    # git stash list is empty since we just created the repo
    result = rollback(repo_root=git_repo)
    
    assert result["success"] is False
    assert "No checkpoint found" in result["error"]
