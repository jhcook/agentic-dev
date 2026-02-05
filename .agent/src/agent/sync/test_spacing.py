
"""
Verification script for Notion Block spacing.
Tests that the _blocks_to_markdown conversion logic maintains correct spacing between different block types (quotes, paragraphs).
"""

from agent.sync.notion import NotionSync
from unittest.mock import patch

def test_spacing():
    with patch("agent.sync.notion.get_secret", return_value="fake"), \
         patch("agent.sync.notion.config"), \
         patch("os.getenv", return_value="fake"):
        sync = NotionSync()
        sync.client = None # Don't need real client
    blocks = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Para 1", "annotations": {"bold": False, "italic": False, "code": False}}]}},
        {"type": "quote", "quote": {"rich_text": [{"plain_text": "Quote 1", "annotations": {"bold": False, "italic": False, "code": False}}]}},
        {"type": "quote", "quote": {"rich_text": [{"plain_text": "Quote 2", "annotations": {"bold": False, "italic": False, "code": False}}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Para 2", "annotations": {"bold": False, "italic": False, "code": False}}]}}
    ]
    
    md = sync._blocks_to_markdown(blocks)
    print("--- MARKDOWN ---")
    print(md)
    print("--- END ---")
    
    # Expect tight quotes
    expected = "Para 1\n\n> Quote 1\n> Quote 2\n\nPara 2"
    if md == expected:
        print("SUCCESS: Spacing is correct.")
    else:
        print("FAILURE: Spacing is incorrect.")
        print(f"Expected:\n{repr(expected)}")
        print(f"Got:\n{repr(md)}")

if __name__ == "__main__":
    test_spacing()
