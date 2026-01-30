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
from unittest.mock import patch
from backend.voice.tools.git import git_stage_changes

@pytest.fixture(autouse=True)
def mock_otel():
    with patch('backend.voice.tools.git.logger') as mock_logger:
        yield mock_logger

def test_git_stage_all():
    with patch("subprocess.run") as mock_run, \
         patch("backend.voice.tools.git.agent_config") as mock_config:
        
        mock_config.repo_root = "/mock/root"
        mock_run.return_value.stdout = ""
        
        result = git_stage_changes.invoke(input={"files": ["."]})
        
        assert "Staged all changes" in result
        mock_run.assert_called_with(
            ["git", "add", "."], 
            capture_output=True, 
            text=True, 
            check=True,
            cwd="/mock/root"
        )

def test_git_stage_specific_file():
    with patch("subprocess.run") as mock_run, \
         patch("backend.voice.tools.git.agent_config") as mock_config:
         
        mock_config.repo_root = "/mock/root"
        mock_run.return_value.stdout = ""
        
        result = git_stage_changes.invoke(input={"files": ["file1.py", "file2.py"]})
        
        assert "Staged: file1.py, file2.py" in result
        mock_run.assert_called_with(
            ["git", "add", "file1.py", "file2.py"], 
            capture_output=True, 
            text=True, 
            check=True,
            cwd="/mock/root"
        )
