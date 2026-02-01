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
from unittest.mock import patch, Mock
import subprocess
from agent.commands.lint import run_markdownlint

@patch("shutil.which")
@patch("subprocess.run")
def test_run_markdownlint_npx_success(mock_run, mock_which):
    # Setup: npx exists found
    mock_which.side_effect = lambda x: "/usr/bin/npx" if x == "npx" else None
    
    files = ["doc.md"]
    success = run_markdownlint(files)
    
    assert success is True
    # Verify npx command
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "npx"
    assert "markdownlint-cli" in args
    assert "doc.md" in args

@patch("shutil.which")
@patch("subprocess.run")
def test_run_markdownlint_missing_deps(mock_run, mock_which):
    # Setup: neither npx nor markdownlint found
    mock_which.return_value = None
    
    files = ["doc.md"]
    success = run_markdownlint(files)
    
    # Should skip gracefuly (return True) but log warning
    assert success is True
    mock_run.assert_not_called()

@patch("shutil.which")
@patch("subprocess.run")
def test_run_markdownlint_failure(mock_run, mock_which):
    # Setup: npx exists, but command fails (lint errors)
    mock_which.side_effect = lambda x: "/usr/bin/npx" if x == "npx" else None
    mock_run.side_effect = subprocess.CalledProcessError(1, ["npx"])
    
    files = ["bad.md"]
    success = run_markdownlint(files)
    
    assert success is False
