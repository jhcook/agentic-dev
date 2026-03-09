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
from agent.core.check.impact import run_impact_analysis

@patch("pathlib.Path.read_text")
@patch("agent.core.config.config.stories_dir", new_callable=MagicMock)
@patch("subprocess.run")
def test_run_impact_analysis_offline(mock_run, mock_stories_dir, mock_read_text, tmp_path):
    mock_stories_dir.rglob.return_value = [tmp_path / "INFRA-123-test.md"]
    mock_read_text.return_value = "# Story Details"
    
    # Mock git diff
    mock_proc = MagicMock()
    mock_proc.stdout = "src/main.py\n"
    mock_run.return_value = mock_proc
    
    with patch("agent.core.dependency_analyzer.DependencyAnalyzer") as mock_analyzer_cls, \
         patch("agent.db.journey_index.get_affected_journeys") as mock_get_journeys, \
         patch("agent.db.journey_index.is_stale", return_value=False), \
         patch("agent.db.journey_index.rebuild_index") as mock_rebuild, \
         patch("sqlite3.connect"):
    
        # Mock dependency analysis
        mock_analyzer = MagicMock()
        mock_analyzer.find_reverse_dependencies.return_value = {"src/main.py": ["tests/test_main.py"]}
        mock_analyzer_cls.return_value = mock_analyzer
        
        # Mock journey map
        mock_get_journeys.return_value = [{"id": "J-1", "tests": ["tests/test_main.py"], "matched_files": ["src/main.py"]}]
        
        result = run_impact_analysis(
            story_id="INFRA-123",
            offline=True,
            base="main",
            update_story=False,
            provider=None,
            rebuild_index=False
        )
        
        assert result["story_id"] == "INFRA-123"
        assert result["is_offline"] is True
        assert "src/main.py" in result["changed_files"]
        assert result["total_impacted"] == 1
        assert "tests/test_main.py" in result["reverse_dependencies"]["src/main.py"]
        assert len(result["affected_journeys"]) == 1
        assert "tests/test_main.py" in result["test_markers"]

@patch("pathlib.Path.read_text")
@patch("agent.core.config.config.stories_dir", new_callable=MagicMock)
@patch("subprocess.run")
def test_run_impact_analysis_ai_error_fallback(mock_run, mock_stories_dir, mock_read_text, tmp_path):
    mock_stories_dir.rglob.return_value = [tmp_path / "INFRA-123-test.md"]
    mock_read_text.return_value = "# Story Details"
    
    mock_proc = MagicMock()
    mock_proc.stdout = "src/main.py\n"
    mock_run.return_value = mock_proc
    
    with patch("agent.core.ai.ai_service.get_completion", side_effect=Exception("API limit")), \
         patch("agent.db.journey_index.get_affected_journeys", return_value=[]), \
         patch("agent.db.journey_index.is_stale", return_value=False), \
         patch("agent.db.journey_index.rebuild_index"), \
         patch("sqlite3.connect"):
        
        result = run_impact_analysis(
            story_id="INFRA-123",
            offline=False,
            base="main",
            update_story=False,
            provider="gemini",
            rebuild_index=False
        )
        
        assert "AI Analysis Failed: API limit" in result["error"]
        assert "Static Impact Analysis" in result["impact_summary"]
