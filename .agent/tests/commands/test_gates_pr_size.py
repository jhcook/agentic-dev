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
from unittest.mock import MagicMock, patch
from agent.commands.gates import check_pr_size

def test_check_pr_size_under_limit():
    """100 lines added → PASS."""
    mock_output = "100\t50\tsrc/main.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        result = check_pr_size(threshold=400)
        assert result.passed is True
        assert "PR size OK" in result.details
        assert "100 additions" in result.details

def test_check_pr_size_over_limit():
    """401 lines added → REJECT."""
    mock_output = "401\t0\tsrc/large_file.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        result = check_pr_size(threshold=400)
        assert result.passed is False
        assert "exceeds 400 lines" in result.details

def test_check_pr_size_net_negative():
    """500 deletions, 450 additions → PASS."""
    mock_output = "450\t500\tsrc/refactor.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        result = check_pr_size(threshold=400)
        assert result.passed is True
        assert "Net-negative change" in result.details
        assert "+450/-500" in result.details

def test_check_pr_size_ignored_files():
    """1000 lines in package-lock.json → PASS."""
    mock_output = "1000\t0\tpackage-lock.json\n10\t0\tsrc/app.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        result = check_pr_size(threshold=400)
        assert result.passed is True
        assert "10 additions" in result.details

def test_check_pr_size_prefix_bypass():
    """'chore(deps): update' with 500 lines → PASS."""
    with patch("subprocess.run") as mock_run:
        # Subprocess shouldn't even be called due to early return
        result = check_pr_size(threshold=400, commit_message="chore(deps): update packages")
        assert result.passed is True
        assert "Bypassed via commit prefix" in result.details
        mock_run.assert_not_called()

def test_check_pr_size_refactor_bypass():
    """'refactor(auto): formatting' with 600 lines → PASS."""
    with patch("subprocess.run") as mock_run:
        result = check_pr_size(threshold=400, commit_message="refactor(auto): bulk format")
        assert result.passed is True
        assert "Bypassed via commit prefix" in result.details

def test_check_pr_size_git_fail():
    """If git fails, we skip the gate (fail-open for robustness)."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = check_pr_size()
        assert result.passed is True
        assert "Skipped — git diff failed" in result.details