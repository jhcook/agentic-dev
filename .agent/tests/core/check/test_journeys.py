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
from agent.core.check.journeys import check_journey_coverage_gate, run_journey_impact_mapping

@patch("agent.core.check.quality.check_journey_coverage")
def test_check_journey_coverage_gate_passed(mock_check_journey_coverage):
    mock_check_journey_coverage.return_value = {
        "linked": 5,
        "total": 5,
        "warnings": [],
        "missing_ids": set()
    }
    
    journey_gate = {"passed": True, "journey_ids": ["J-123"]}
    result = check_journey_coverage_gate(journey_gate)
    
    assert result["passed"] is True
    assert result["linked"] == 5
    assert result["total"] == 5
    assert not result["warnings"]
    assert not result["missing_ids"]
    assert result["error"] is None

@patch("agent.core.check.quality.check_journey_coverage")
def test_check_journey_coverage_gate_failed_linked(mock_check_journey_coverage):
    mock_check_journey_coverage.return_value = {
        "linked": 4,
        "total": 5,
        "warnings": ["J-123 has no tests"],
        "missing_ids": {"J-123", "J-456"}
    }
    
    journey_gate = {"passed": True, "journey_ids": ["J-123"]}
    result = check_journey_coverage_gate(journey_gate)
    
    assert result["passed"] is False
    assert result["linked"] == 4
    assert result["total"] == 5
    assert len(result["warnings"]) == 1
    assert "J-123" in result["missing_ids"]
    assert result["error"] is not None
    assert "J-123 have no tests" in result["error"]

@patch("agent.db.journey_index.is_stale")
@patch("agent.db.journey_index.rebuild_index")
@patch("agent.db.journey_index.get_affected_journeys")
@patch("sqlite3.connect")
@patch("subprocess.run")
def test_run_journey_impact_mapping(mock_subprocess, mock_connect, mock_get_affected_journeys, mock_rebuild_index, mock_is_stale):
    mock_is_stale.return_value = True
    mock_rebuild_index.return_value = {"journey_count": 10, "file_glob_count": 20}
    
    mock_proc = MagicMock()
    mock_proc.stdout = "src/main.py\n"
    mock_subprocess.return_value = mock_proc
    
    mock_get_affected_journeys.return_value = [{"id": "J-1", "tests": ["test_main.py"]}]
    
    db_mock = MagicMock()
    mock_connect.return_value = db_mock
    
    result = run_journey_impact_mapping(base="main")
    
    assert result["rebuilt_index"] is True
    assert "src/main.py" in result["changed_files"]
    assert len(result["affected_journeys"]) == 1
    assert "test_main.py" in result["test_files_to_run"]
    
    db_mock.close.assert_called_once()
