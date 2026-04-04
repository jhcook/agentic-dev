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
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent.core.implement.guards import check_api_surface_renames

def test_check_api_surface_renames_private_ignored():
    """AC-4: Verify that symbols starting with an underscore are ignored."""
    blocks = [{
        "file": "src/logic.py",
        "search": "def _internal_helper():\n    return 1",
        "replace": "def _refactored_helper():\n    return 1"
    }]
    # Even if grep found consumers, it shouldn't run for private symbols
    with patch("subprocess.run") as mock_run:
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0
        mock_run.assert_not_called()

def test_check_api_surface_renames_implementation_only():
    """AC-3: Verify that changing function body without renaming passes."""
    blocks = [{
        "file": "src/api.py",
        "search": "def get_data():\n    return []",
        "replace": "def get_data():\n    # New implementation\n    return None"
    }]
    errors = check_api_surface_renames(blocks, Path("/tmp"))
    assert len(errors) == 0

def test_check_api_surface_renames_orphaned_consumer():
    """AC-1: Verify rename with live consumer not in runbook triggers error."""
    blocks = [{
        "file": "src/executor.py",
        "search": "class TaskExecutor:\n    pass",
        "replace": "class ToolExecutor:\n    pass"
    }]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding the old name in a file NOT in the runbook
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/main.py\n"
        )
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 1
        assert "'TaskExecutor' was renamed to 'ToolExecutor'" in errors[0]
        assert "src/main.py" in errors[0]

def test_check_api_surface_renames_covered_consumer():
    """AC-2: Verify rename with consumer covered in runbook passes."""
    blocks = [
        {
            "file": "src/executor.py",
            "search": "class TaskExecutor:\n    pass",
            "replace": "class ToolExecutor:\n    pass"
        },
        {
            "file": "src/main.py",
            "search": "TaskExecutor()",
            "replace": "ToolExecutor()"
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding the consumer in main.py (which is in our runbook)
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/main.py\n"
        )
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0

def test_check_api_surface_renames_no_consumers():
    """Verify rename with no consumers in codebase passes."""
    blocks = [{
        "file": "src/unused.py",
        "search": "def legacy_func():\n    pass",
        "replace": "def modern_func():\n    pass"
    }]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding nothing (returncode 1)
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0
