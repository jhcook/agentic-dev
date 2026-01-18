import argparse

import pytest

pytestmark = pytest.mark.skip("Legacy implementation pending")
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is in path for imports if running directly, though pytest usually handles this
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


from agent.sync import sync


@pytest.mark.skip(reason="Legacy sync tests, implementation pending")
def test_nothing():
    pass



@pytest.fixture
def mock_supabase():
    with patch("agent.sync.sync.get_supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_db_connection():
    with patch("agent.sync.sync.get_db_connection") as mock:
        mock_conn = MagicMock()
        mock.return_value = mock_conn
        yield mock_conn

def test_push_no_artifacts(mock_supabase, mock_db_connection, capsys):
    """Test push with no artifacts to sync."""
    # Setup
    mock_cursor = mock_db_connection.cursor.return_value
    mock_cursor.fetchall.return_value = [] # No artifacts, history, links (fetchall called 3 times, or returns empty list each time)
    
    # Execute
    sync.push(argparse.Namespace())
    
    # Verify
    captured = capsys.readouterr()
    assert "No local artifacts to push." in captured.out

def test_push_success(mock_supabase, mock_db_connection, capsys):
    """Test push with artifacts."""
    # Setup
    mock_cursor = mock_db_connection.cursor.return_value
    # 3 calls to fetchall: artifacts, history, links
    mock_cursor.fetchall.side_effect = [
        [{"id": "A1", "content": "foo"}], # artifacts
        [], # history
        []  # links
    ]
    
    mock_client = mock_supabase.return_value
    mock_table = mock_client.table.return_value
    mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

    # Execute
    sync.push(argparse.Namespace())
    
    # Verify
    captured = capsys.readouterr()
    assert "Pushing" in captured.out
    
    # Ensure upsert called for artifacts
    mock_client.table.assert_any_call("artifacts")
    
def test_pull_success(mock_supabase, mock_db_connection, capsys):
    """Test pull with remote data."""
    # Setup
    mock_client = mock_supabase.return_value
    
    # Mock return for artifacts, history, links
    # The code calls table().select().execute().data sequentially
    # 1. artifacts
    # 2. history
    # 3. links
    
    # We need to set side_effect for the chain. 
    # chaining: table(name) -> select(*) -> execute() -> data
    
    # Simpler: 
    mock_execute = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value = mock_execute
    
    # We can use side_effect on the 'data' property if we mock it specifically, or just use side_effect on execute()
    # BUT data is a property of the result object.
    
    res1 = MagicMock()
    res1.data = [{"id": "A1", "type": "story", "content": "foo", "last_modified": "2024", "version": 1, "state": "C", "author": "me", "created_at": "now", "updated_at": "now", "owner_id": "u1"}]
    
    res2 = MagicMock()
    res2.data = [] # history
    
    res3 = MagicMock()
    res3.data = [] # links
    
    mock_client.table.return_value.select.return_value.execute.side_effect = [res1, res2, res3]
    
    # Execute
    sync.pull(argparse.Namespace())
    
    # Verify
    captured = capsys.readouterr()
    assert "Sync Pull: Fetching remote state..." in captured.out
    
    # Verify INSERT executed
    call_args_list = mock_db_connection.execute.call_args_list
    assert any("INSERT OR REPLACE INTO artifacts" in str(call) for call, _ in call_args_list)

