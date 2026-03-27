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
Unit tests for the testing tool domain.
"""

import pytest
from unittest.mock import patch, MagicMock
from agent.tools.testing import run_tests

@patch("subprocess.run")
def test_run_tests_structured_parsing(mock_run):
    """Verify pytest output is parsed into structured JSON (AC-5)."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = """============================= test session starts =============================
platform darwin -- Python 3.12.3, pytest-8.2.1, pluggy-1.5.0
rootdir: /tmp/test-repo
collected 8 items

tests/test_a.py ..                                                       [ 25%]
tests/test_b.py .F                                                       [ 50%]
tests/test_c.py E..                                                      [ 100%]

=================================== ERRORS ====================================
_________________________ ERROR at setup of test_error ________________________
... stack trace ...
================================== FAILURES ===================================
__________________________________ test_fail __________________________________
... stack trace ...
=========================== 3 passed, 1 failed, 1 error in 0.42s ===========================
"""
    mock_proc.stderr = ""
    mock_run.return_value = mock_proc

    result = run_tests("tests")
    
    assert result["success"] is True
    assert result["output"]["passed"] == 3
    assert result["output"]["failed"] == 1
    assert result["output"]["errors"] == 1
    assert isinstance(result["output"]["coverage_pct"], float)

@patch("subprocess.run")
def test_run_tests_failure_status(mock_run):
    """Verify result reflects non-zero exit code."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = "... 1 failed ..."
    mock_proc.stderr = ""
    mock_run.return_value = mock_proc

    result = run_tests("tests")
    assert result["success"] is False
