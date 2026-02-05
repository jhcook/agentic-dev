
"""
Unit tests for Smart Status Preservation logic.
Ensures that local status (e.g. APPROVED) is preserved during sync pulls
even when Notion returns DRAFT, provided the content body is identical.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from textwrap import dedent
from agent.sync.notion import NotionSync

def test_smart_status_preservation():
    """
    Verifies that if local and remote content (normalized) matches, 
    but status differs, the LOCAL status is preserved.
    """
    with patch("agent.sync.notion.get_secret", return_value="fake"), \
         patch("agent.sync.notion.config"), \
         patch("os.getenv", return_value="fake"):
        
        with patch.object(NotionSync, "_load_state", return_value={}):
            syncer = NotionSync()
            
    # MOCK Confirm.ask to avoid OSError if conflicts DO occur (failsafe)
    # But ideally we want NO conflict.
    with patch("rich.prompt.Confirm.ask", return_value=False): 
        # 1. Setup Content
        # Normalized content will match
        body_content = "The actual content of the story."
        
        # 2. Local File State (APPROVED)
        local_content = dedent(f"""\
        # TEST-123: My Title
        
        ## State

        APPROVED

        {body_content}
        """)

        # 3. Remote/Notion State (DRAFT)
        # The puller constructs this content string internally from blocks
        remote_constructed_content = dedent(f"""\
        # TEST-123: My Title

        ## State

        DRAFT

        {body_content}
        """)

        # Mock blocks to markdown conversion
        syncer._blocks_to_markdown = MagicMock(return_value=body_content) 
        # Note: _process_pull_page constructs the full content string itself, 
        # using _blocks_to_markdown only for the body.
        # We need to ensure the constructed 'content' variable inside the method 
        # has the DRAFT status.
        
        # The method does:
        # content = f"# {art_id}: {title}\n\n"
        # content += f"## State\n\n{status}\n\n"
        # content += markdown_body
        
        # So we need to mock the page properties to return DRAFT
        page = {
            "id": "p1",
            "properties": {
                "ID": {"rich_text": [{"plain_text": "TEST-123"}]},
                "Title": {"title": [{"plain_text": "My Title"}]},
                "Status": {"select": {"name": "DRAFT"}} 
            }
        }
        
        syncer.client = MagicMock()
        syncer.client.retrieve_block_children.return_value = []
        
        # Mock Filesystem
        mock_path = MagicMock(spec=Path)
        mock_target_file = MagicMock(spec=Path)
        mock_dir = MagicMock(spec=Path)
        mock_path.__truediv__.return_value = mock_dir
        mock_dir.__truediv__.return_value = mock_target_file
        
        # File exists!
        mock_target_file.exists.return_value = True
        mock_target_file.read_text.return_value = local_content
        
        # Mock glob to return the file (so it finds it)
        mock_dir.glob.return_value = [mock_target_file]
        mock_target_file.name = "TEST-123-my-title.md"

        # MOCK _parse_status to extract APPROVED from local_content
        # (Since we are testing _process_pull_page, it might call _parse_status implicitly? 
        # No, we need to ensure the logic reads it. Actually _process_pull_page reads text 
        # but doesn't call _parse_status on it by default, we need to add that logic or regex.)
        
        # Run
        syncer._process_pull_page(page, mock_path, "Stories", force=False)
        
        # Verify Write
        # The KEY assertion: content written to file should have APPROVED, not DRAFT
        args, _ = mock_target_file.write_text.call_args
        content_written = args[0]
        
        print("DEBUG: Written Content:\n", content_written)
        
        assert "APPROVED" in content_written
        assert "DRAFT" not in content_written
