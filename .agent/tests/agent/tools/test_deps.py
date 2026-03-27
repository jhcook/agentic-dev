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
Unit tests for the dependency tool domain.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from agent.tools.deps import add_dependency, audit_dependencies

@patch("subprocess.run")
def test_add_dependency_uv(mock_run):
    """Verify uv add is called correctly."""
    mock_run.return_value = MagicMock(returncode=0, stdout="uv add success", stderr="")
    
    result = add_dependency("fastapi")
    
    assert result["success"] is True
    assert "uv" in mock_run.call_args[0][0]
    assert "add" in mock_run.call_args[0][0]
    assert "fastapi" in mock_run.call_args[0][0]

@patch("subprocess.run")
def test_audit_dependencies_json(mock_run):
    """Verify pip-audit output is parsed as JSON."""
    audit_data = [{
        "name": "insecure-pkg", 
        "version": "1.0", 
        "vulns": [{
            "id": "CVE-2023-1234",
            "fix_versions": ["1.1"],
            "aliases": ["GHSA-xxxx"],
            "description": "A bad vulnerability."
        }]
    }]
    mock_run.return_value = MagicMock(
        returncode=0, 
        stdout=json.dumps(audit_data), 
        stderr=""
    )
    
    result = audit_dependencies()
    
    assert result["success"] is True
    assert result["output"] == audit_data
