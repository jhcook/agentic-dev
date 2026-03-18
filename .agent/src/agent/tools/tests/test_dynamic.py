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

"""Tests for the core dynamic tool engine."""

import ast
import pytest
from pathlib import Path
from agent.tools import dynamic

def test_security_scan_rejects_eval():
    """Verify that eval() calls are rejected by the security scanner."""
    code = "def my_tool():\n    eval('print(1)')"
    tree = ast.parse(code)
    errors = dynamic._security_scan(tree, code)
    assert any("Usage of 'eval' is forbidden" in e for e in errors)

def test_security_scan_rejects_os_system():
    """Verify that os.system() calls are rejected by the security scanner."""
    code = "import os\ndef my_tool():\n    os.system('ls')"
    tree = ast.parse(code)
    errors = dynamic._security_scan(tree, code)
    assert any("Usage of 'os.system' (or similar) is restricted" in e for e in errors)

def test_security_scan_rejects_subprocess_import():
    """Verify that subprocess imports are rejected by the security scanner."""
    code = "import subprocess\ndef my_tool():\n    subprocess.run(['ls'])"
    tree = ast.parse(code)
    errors = dynamic._security_scan(tree, code)
    assert any("Usage of 'subprocess' is restricted" in e for e in errors)

def test_security_scan_allows_noqa_bypass():
    """Verify that the # NOQA: SECURITY_RISK comment bypasses the scan."""
    code = "# NOQA: SECURITY_RISK\nimport os\nos.system('ls')"
    tree = ast.parse(code)
    errors = dynamic._security_scan(tree, code)
    assert len(errors) == 0

def test_path_containment_rejects_traversal(tmp_path):
    """Verify that path traversal attempts are caught by create_tool."""
    with pytest.raises(dynamic.PathTraversalError):
        dynamic.create_tool("../../../evil.py", "print('hello')")

def test_create_tool_workflow(tmp_path, monkeypatch):
    """
    Integration test: create a tool and verify it can be imported.
    Note: We mock the custom tools dir to avoid polluting the repo during tests.
    """
    monkeypatch.setattr(dynamic, "_get_custom_tools_dir", lambda: tmp_path)
    
    code = "def test_tool():\n    return 'success'"
    result = dynamic.create_tool("test_dynamic_tool.py", code)
    
    assert "Success: Tool created" in result
    assert (tmp_path / "test_dynamic_tool.py").exists()