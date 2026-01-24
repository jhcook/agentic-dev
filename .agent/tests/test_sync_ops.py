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

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is in path for imports if running directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agent.sync import sync


@pytest.fixture
def mock_supabase():
    with patch("agent.sync.sync.get_supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_db_client():
    with patch("agent.sync.sync.get_all_artifacts_content") as mock_get, \
         patch("agent.sync.sync.upsert_artifact") as mock_upsert:
        yield {"get": mock_get, "upsert": mock_upsert}

def test_nothing():
    pass

def test_push_no_artifacts(mock_supabase, mock_db_client, capsys):
    """Test push with no artifacts to sync."""
    # Setup
    mock_db_client["get"].return_value = []
    
    # Execute
    sync.push(verbose=False)
    
    # Verify
    captured = capsys.readouterr()
    assert "No local artifacts to push." in captured.out

def test_push_success(mock_supabase, mock_db_client, capsys):
    """Test push with artifacts."""
    # Setup
    mock_db_client["get"].return_value = [
        {"id": "A1", "type": "story", "content": "foo", "version": 1, "state": "open", "author": "me"}
    ]
    
    mock_client = mock_supabase.return_value
    mock_table = mock_client.table.return_value
    mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

    # Execute
    sync.push(verbose=True)
    
    # Verify
    captured = capsys.readouterr()
    assert "Pushing 1 artifacts" in captured.out
    
    # Ensure upsert called for artifacts
    mock_client.table.assert_any_call("artifacts")
    # Verify the payload
    # mock_client.table("artifacts").upsert(...)
    # We can inspect the calls if needed
    
def test_pull_success(mock_supabase, mock_db_client, capsys):
    """Test pull with remote data."""
    # Setup
    mock_client = mock_supabase.return_value
    
    # Mock total count
    mock_client.table.return_value.select.return_value.execute.return_value.count = 1
    
    # Mock page fetch
    page_data = [{"id": "A1", "type": "story", "content": "foo", "version": 1, "state": "C", "author": "remote"}]
    mock_client.table.return_value.select.return_value.range.return_value.execute.return_value.data = page_data
    
    # Execute
    sync.pull(verbose=True)
    
    # Verify
    captured = capsys.readouterr()
    assert "Syncing 1 artifacts" in captured.out
    
    # Verify upsert_artifact called
    mock_db_client["upsert"].assert_called_with(
        id="A1", type="story", content="foo", author="remote"
    )
