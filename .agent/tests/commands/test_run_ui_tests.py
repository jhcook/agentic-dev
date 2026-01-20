
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

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.check import run_ui_tests

# Create a Typer app to test the command function
app = typer.Typer()
app.command()(run_ui_tests)
runner = CliRunner()

@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which") as mock:
        yield mock

@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock:
        yield mock

@pytest.fixture
def mock_path_rglob():
    with patch("pathlib.Path.rglob") as mock:
        yield mock

@pytest.fixture
def mock_path_exists():
    with patch("pathlib.Path.exists") as mock:
        yield mock

@pytest.fixture
def mock_path_is_dir():
    with patch("pathlib.Path.is_dir") as mock:
        yield mock

def test_maestro_not_installed(mock_shutil_which):
    mock_shutil_which.return_value = None
    result = runner.invoke(app, ["INFRA-009"])
    assert result.exit_code == 1
    assert "Maestro CLI is not installed" in result.stdout

def test_no_test_flows_found(mock_shutil_which, mock_path_exists, mock_path_is_dir, mock_path_rglob):
    mock_shutil_which.return_value = "/usr/bin/maestro"
    mock_path_exists.return_value = True
    mock_path_is_dir.return_value = True
    mock_path_rglob.return_value = []
    
    result = runner.invoke(app, ["INFRA-009"])
    assert result.exit_code == 0
    assert "No .yaml/.yml test flows found" in result.stdout

def test_run_success(mock_shutil_which, mock_path_exists, mock_path_is_dir, mock_path_rglob, mock_subprocess_run):
    mock_shutil_which.return_value = "/usr/bin/maestro"
    mock_path_exists.return_value = True
    mock_path_is_dir.return_value = True
    
    # Mock finding one flow
    mock_flow = MagicMock(spec=Path)
    mock_flow.name = "login_flow.yaml"
    mock_flow.__str__.return_value = "tests/ui/login_flow.yaml"
    # Path("tests/ui") -> *.yaml, *.yml | Path(".maestro") -> *.yaml, *.yml
    # Total 4 calls.
    mock_path_rglob.side_effect = [[mock_flow], [], [], []] 
    
    # Mock subprocess success
    mock_subprocess_run.return_value.returncode = 0
    
    result = runner.invoke(app, ["INFRA-009"])
    
    assert result.exit_code == 0
    assert "Found 1 test flows" in result.stdout
    assert "PASSED" in result.stdout
    mock_subprocess_run.assert_called_once()

def test_run_failure(mock_shutil_which, mock_path_exists, mock_path_is_dir, mock_path_rglob, mock_subprocess_run):
    mock_shutil_which.return_value = "/usr/bin/maestro"
    mock_path_exists.return_value = True
    mock_path_is_dir.return_value = True
    
    mock_flow = MagicMock(spec=Path)
    mock_flow.name = "login_flow.yaml"
    mock_flow.__str__.return_value = "tests/ui/login_flow.yaml"
    
    # 4 calls to rglob
    mock_path_rglob.side_effect = [[mock_flow], [], [], []]
    
    # Mock subprocess failure
    mock_subprocess_run.return_value.returncode = 1
    
    result = runner.invoke(app, ["INFRA-009"])
    
    assert result.exit_code == 1
    assert "FAILED" in result.stdout
    assert "Failed: 1" in result.stdout

def test_filter_argument(mock_shutil_which, mock_path_exists, mock_path_is_dir, mock_path_rglob, mock_subprocess_run):
    mock_shutil_which.return_value = "/usr/bin/maestro"
    mock_path_exists.return_value = True
    mock_path_is_dir.return_value = True
    
    mock_flow1 = MagicMock(spec=Path)
    mock_flow1.name = "login_flow.yaml"
    mock_flow2 = MagicMock(spec=Path)
    mock_flow2.name = "signup_flow.yaml"
    
    # 4 calls to rglob
    mock_path_rglob.side_effect = [[mock_flow1, mock_flow2], [], [], []]
    
    mock_subprocess_run.return_value.returncode = 0
    
    # Filter for 'login'
    result = runner.invoke(app, ["INFRA-009", "--filter", "login"])
    
    assert result.exit_code == 0
    assert "Found 1 test flows" in result.stdout
    assert "login_flow.yaml" in result.stdout
    assert "signup_flow.yaml" not in result.stdout

