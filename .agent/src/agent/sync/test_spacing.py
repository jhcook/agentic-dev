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
