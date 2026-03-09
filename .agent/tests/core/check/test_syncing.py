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
from agent.core.check.syncing import sync_oracle_pattern

@patch("agent.sync.notion.NotionSync")
@patch("agent.sync.notebooklm.ensure_notebooklm_sync")
def test_sync_oracle_pattern_all_success(mock_ensure_notebooklm, mock_notion_sync):
    mock_notion_sync.return_value = MagicMock()
    
    async def mock_ensure(*args, **kwargs):
        return "SUCCESS"
    mock_ensure_notebooklm.side_effect = mock_ensure
    
    result = sync_oracle_pattern()
    
    assert result["notion_ready"] is True
    assert "Notion sync ready" in result["notion_status"]
    assert result["notebooklm_ready"] is True
    assert "NotebookLM sync ready" in result["notebooklm_status"]
    assert result["vector_db_ready"] is False

@patch("agent.sync.notion.NotionSync")
@patch("agent.sync.notebooklm.ensure_notebooklm_sync")
@patch("agent.db.journey_index.JourneyIndex")
def test_sync_oracle_pattern_fallback_to_vector_db(mock_journey_index, mock_ensure_notebooklm, mock_notion_sync):
    mock_notion_sync.side_effect = Exception("Notion down")
    
    async def mock_ensure(*args, **kwargs):
        raise Exception("NotebookLM down")
    mock_ensure_notebooklm.side_effect = mock_ensure
    
    mock_idx_instance = MagicMock()
    mock_journey_index.return_value = mock_idx_instance
    
    result = sync_oracle_pattern()
    
    assert result["notion_ready"] is False
    assert "Notion sync unreachable" in result["notion_status"]
    assert result["notebooklm_ready"] is False
    assert "NotebookLM sync unreachable" in result["notebooklm_status"]
    
    assert result["vector_db_ready"] is True
    assert "Local Vector DB ready" in result["vector_db_status"]
    mock_idx_instance.build.assert_called_once()
