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
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.core.check.testing import run_smart_test_selection

def test_run_smart_test_selection_skip():
    result = run_smart_test_selection(base=None, skip_tests=True, interactive=False, ignore_tests=False)
    assert result["passed"] is True
    assert result["skipped"] is True
    assert len(result["test_commands"]) == 0

@patch("subprocess.run")
def test_run_smart_test_selection_git_error(mock_run):
    # Simulate a git diff failure
    mock_run.side_effect = Exception("git failed")
    result = run_smart_test_selection(base="main", skip_tests=False, interactive=False, ignore_tests=False)
    
    assert result["passed"] is False
    assert "git failed" in result["error"]

@patch("subprocess.run")
@patch("agent.core.dependency_analyzer.DependencyAnalyzer")
@patch("pathlib.Path.rglob")
@patch("pathlib.Path.exists")
def test_run_smart_test_selection_backend_changes(mock_exists, mock_rglob, mock_analyzer, mock_run, tmp_path):
    # Mocking git output: a backend file changed
    mock_proc = MagicMock()
    mock_proc.stdout = "backend/main.py\n"
    mock_run.return_value = mock_proc
    
    # Mock finding test files
    mock_rglob.return_value = [tmp_path / "backend/test_main.py"]
    
    # Test file relies on changed file
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.get_file_dependencies.return_value = {Path("backend/main.py")}
    mock_analyzer.return_value = mock_analyzer_instance
    
    # Ensure package.json does not exist for web/mobile tests
    mock_exists.return_value = False
    
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = run_smart_test_selection(base="main", skip_tests=False, interactive=False, ignore_tests=False)
        
    assert result["passed"] is True
    assert len(result["test_commands"]) == 1
    assert result["test_commands"][0]["name"] == "Python Tests"
    
    cmd_args = result["test_commands"][0]["cmd"]
    assert "-m" in cmd_args
    assert "pytest" in cmd_args

@patch("subprocess.run")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.read_text")
def test_run_smart_test_selection_mobile_changes(mock_read_text, mock_exists, mock_run, tmp_path):
    mock_proc = MagicMock()
    mock_proc.stdout = "mobile/App.tsx\n"
    mock_run.return_value = mock_proc
    
    # Ensure package.json and node_modules exist
    mock_exists.return_value = True
    mock_read_text.return_value = '{"scripts": {"lint": "eslint .", "test": "jest"}}'
    
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = run_smart_test_selection(base="main", skip_tests=False, interactive=False, ignore_tests=False)
        
    assert result["passed"] is True
    assert len(result["test_commands"]) == 2
    names = [c["name"] for c in result["test_commands"]]
    assert "Mobile Lint" in names
    assert "Mobile Tests" in names
