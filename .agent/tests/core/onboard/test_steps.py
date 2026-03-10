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
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from agent.core.onboard import steps

@pytest.fixture
def console():
    return Console()

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_success(mock_find_spec, mock_which, mock_logger, console):
    """Test check_dependencies returns True when all found."""
    mock_which.return_value = "/usr/bin/tool"
    mock_find_spec.return_value = True

    result = steps.check_dependencies(console)
    assert result is True
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
@patch("agent.core.onboard.steps.shutil.which")
@patch("importlib.util.find_spec")
def test_check_dependencies_missing_binary(mock_find_spec, mock_which, mock_logger, console):
    """Test check_dependencies returns False when a binary is missing."""
    mock_find_spec.return_value = True
    
    # Missing git
    def which_side_effect(cmd):
        if cmd == "git":
            return None
        return "/usr/bin/tool"
    
    mock_which.side_effect = which_side_effect

    result = steps.check_dependencies(console)
    assert result is False
    mock_logger.info.assert_called_with("Starting dependency check", extra={"step": "check_dependencies"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_creates_dir(mock_logger, console, tmp_path):
    """Test ensure_agent_directory creates a missing directory."""
    expected_dir = tmp_path / ".agent"
    assert not expected_dir.exists()
    
    steps.ensure_agent_directory(console, project_root=tmp_path)
    assert expected_dir.is_dir()
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_agent_directory_fails_if_file(mock_logger, console, tmp_path):
    """Test ensure_agent_directory exits if .agent is a file."""
    expected_dir = tmp_path / ".agent"
    expected_dir.touch()
    
    with pytest.raises(typer.Exit) as excinfo:
        steps.ensure_agent_directory(console, project_root=tmp_path)
    assert excinfo.value.exit_code == 1
    mock_logger.info.assert_called_with("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})

@patch("agent.core.onboard.steps.logger")
def test_ensure_gitignore_creates_file(mock_logger, console, tmp_path):
    """Test ensure_gitignore creates a .gitignore explicitly."""
    gitignore = tmp_path / ".gitignore"
    assert not gitignore.exists()
    
    steps.ensure_gitignore(console, project_root=tmp_path)
    assert gitignore.is_file()
    assert ".env" in gitignore.read_text()
    mock_logger.info.assert_called_with("Ensuring agent metadata is gitignored", extra={"step": "ensure_gitignore"})
