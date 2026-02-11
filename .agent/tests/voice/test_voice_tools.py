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
import os
import sys

# Add src to path if needed, though pytest usually handles it if configured correctly
# Assuming running from repo root

from backend.voice.tools.qa import run_backend_tests, run_frontend_lint
from backend.voice.tools.security import scan_secrets_in_content
from backend.voice.tools.observability import get_recent_logs

def test_run_backend_tests():
    with patch("backend.voice.tools.qa.subprocess.Popen") as mock_popen, \
         patch("backend.voice.tools.qa.os.path.exists", return_value=True):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["Test passed\n", ""]
        mock_process.stderr.readline.side_effect = [""]
        mock_process.stdout.close = MagicMock()
        mock_process.stderr.close = MagicMock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        # Use invoke with args dict
        result = run_backend_tests.invoke({"path": ".agent/tests/"})
        assert "Test passed" in result
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert ".venv/bin/pytest" in args or "pytest" in args

def test_run_frontend_lint_missing_dir():
    with patch("os.path.exists", side_effect=lambda p: False if ".agent/src/web" in p else True):
        # Tool call with no args
        result = run_frontend_lint.invoke({})
        assert "not found" in result

def test_run_frontend_lint_success():
    with patch("subprocess.run") as mock_run:
        with patch("os.path.exists", return_value=True):
            mock_run.return_value.stdout = "Lint success"
            mock_run.return_value.stderr = ""
            result = run_frontend_lint.invoke({})
            assert "Lint success" in result

def test_scan_secrets_clean():
    content = "just some code\nprint('hello')"
    result = scan_secrets_in_content.invoke({"content": content})
    assert "No obvious secrets found" in result

def test_scan_secrets_detected():
    content = "my_api_key = 'sk-1234567890abcdef12345678'"
    result = scan_secrets_in_content.invoke({"content": content})
    assert "Potential API Key found" in result
    assert "sk-12345" not in result

def test_get_recent_logs():
    with patch("subprocess.run") as mock_run:
        with patch("os.path.exists", return_value=True):
            mock_run.return_value.stdout = "Log entry 1\nLog entry 2"
            result = get_recent_logs.invoke({"lines": 2})
            assert "Log entry 1" in result
            assert "Log entry 2" in result
