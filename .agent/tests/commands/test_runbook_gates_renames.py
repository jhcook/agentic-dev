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

"""Gate integration tests for INFRA-179: API surface rename detection.

These tests verify check_api_surface_renames produces the correct error messages
and passes results into the gate loop. Full run_generation_gates integration is
not tested here due to signature complexity; that is covered by the wider
journey tests (JRN-023).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent.core.implement.guards import check_api_surface_renames


def _make_blocks(*pairs):
    """Helper: pairs of (file, search_code, replace_code)."""
    return [{"file": f, "search": s, "replace": r} for f, s, r in pairs]


def test_rename_with_orphaned_consumer_triggers_correction():
    """Gate 1c: rename with consumer NOT in runbook → error message returned."""
    blocks = _make_blocks(
        (
            "src/executor.py",
            "class TaskExecutor:\n    pass",
            "class ToolExecutor:\n    pass",
        )
    )
    with patch("agent.core.implement.guards.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/runbook_generation.py\n",
        )
        errors = check_api_surface_renames(blocks, Path("/tmp"))

    assert len(errors) == 1
    assert "TaskExecutor" in errors[0]
    assert "src/runbook_generation.py" in errors[0]


def test_rename_with_covered_consumer_passes():
    """Gate 1c: rename with consumer covered in the same runbook → no error."""
    blocks = _make_blocks(
        (
            "src/executor.py",
            "class TaskExecutor:\n    pass",
            "class ToolExecutor:\n    pass",
        ),
        (
            "src/runbook_generation.py",
            "from executor import TaskExecutor",
            "from executor import ToolExecutor",
        ),
    )
    with patch("agent.core.implement.guards.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/runbook_generation.py\n",
        )
        errors = check_api_surface_renames(blocks, Path("/tmp"))

    assert errors == []


def test_rename_with_no_consumers_passes():
    """Gate 1c: rename of symbol with zero consumers → no error."""
    blocks = _make_blocks(
        (
            "src/unused.py",
            "def legacy_func():\n    pass",
            "def modern_func():\n    pass",
        )
    )
    with patch("agent.core.implement.guards.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        errors = check_api_surface_renames(blocks, Path("/tmp"))

    assert errors == []
