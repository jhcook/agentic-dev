
"""
Regression test for the Sync Fix logic.
Verifies that the sync engine correctly strips locally-inserted headers (e.g. ## State)
to prevent duplication when re-syncing from Notion.
"""

import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from agent.sync.notion import NotionSync

def test_sync_fix_applied():
    """
    Verifies that the actual NotionSync class now correctly strips mismatched statuses.
    """
    with patch("agent.sync.notion.get_secret", return_value="fake"), \
         patch("agent.sync.notion.config"), \
         patch("os.getenv", return_value="fake"):
        
        # Patch _load_state to avoid file read
        with patch.object(NotionSync, "_load_state", return_value={}):
            syncer = NotionSync()
            
    # Mock the page and content
    page = {
        "id": "p1",
        "properties": {
            "ID": {"rich_text": [{"plain_text": "TEST-123"}]},
            "Title": {"title": [{"plain_text": "My Title"}]},
            "Status": {"select": {"name": "DRAFT"}} # Property is DRAFT
        }
    }
    
    # Body has "APPROVED" (mismatch)
    stale_body = """# TEST-123: My Title

## State

APPROVED

## Description

Real content.
"""
    
    syncer._blocks_to_markdown = MagicMock(return_value=stale_body)
    syncer.client = MagicMock()
    syncer.client.retrieve_block_children.return_value = []
    
    # Mock Path operations
    mock_path = MagicMock(spec=Path)
    mock_target_file = MagicMock(spec=Path)
    # When (base_dir / scope) is called -> returns dir. When dir / filename -> returns file
    mock_dir = MagicMock(spec=Path)
    mock_path.__truediv__.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_target_file
    
    mock_target_file.exists.return_value = False # New file
    
    # Run
    syncer._process_pull_page(page, mock_path, "Stories", force=True)
    
    # Verify write_text called with correct content
    args, _ = mock_target_file.write_text.call_args
    content_written = args[0]
    
    print("DEBUG: Written Content:\n", content_written)
    
    assert "DRAFT" in content_written # From property
    assert "APPROVED" not in content_written # Should be stripped from body
    assert "Real content" in content_written
