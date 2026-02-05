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

import unittest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from agent.sync.notion import NotionSync

class TestNotionSync(unittest.TestCase):
    
    def test_pull_stories(self):
        with patch("agent.sync.notion.get_secret", return_value="fake_token"), \
             patch("agent.sync.notion.NotionClient") as MockClient, \
             patch("rich.prompt.Confirm.ask", return_value=False), \
             patch("agent.core.config.config") as mock_config:
            
            # Setup Instance
            sync = NotionSync()
            sync.client = MockClient.return_value
            sync.state = {"Stories": "db_stories"}
            
            # Configuration
            mock_config.stories_dir = Path("/tmp/stories")
            
            # Mock Notion Page
            mock_page = {
                "id": "page_id_1",
                "properties": {
                    "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                    "Title": {"title": [{"plain_text": "Test Story"}]},
                    "Status": {"select": {"name": "IN_PROGRESS"}}
                }
            }
            sync.client.query_database.return_value = [mock_page]
            
            # Mock Content
            mock_block = {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Content", "annotations": {"bold": False, "italic": False, "code": False}}]}
            }
            sync.client.retrieve_block_children.return_value = [mock_block]

            # Mock File Ops
            with patch.object(Path, "mkdir") as mock_mkdir, \
                 patch.object(Path, "write_text") as mock_write, \
                 patch.object(Path, "exists", return_value=False): # No conflict
                
                 sync.pull()
                 
                 # Verify strict call
                 sync.client.query_database.assert_called_with("db_stories", filter=None)
                 
                 mock_write.assert_called()
                 args, _ = mock_write.call_args
                 content = args[0]
                 self.assertIn("# INFRA-054: Test Story", content)
                 # Check for State with flexible whitespace or exact match
                 self.assertIn("## State\n\nIN_PROGRESS", content)

    def test_pull_conflict_overwrite(self):
        with patch("agent.sync.notion.get_secret", return_value="fake_token"), \
             patch("agent.sync.notion.NotionClient") as MockClient, \
             patch("rich.prompt.Confirm.ask") as mock_confirm, \
             patch("agent.core.config.config") as mock_config:

            sync = NotionSync()
            sync.client = MockClient.return_value
            sync.state = {"Stories": "db_stories"}
            
            mock_config.stories_dir = Path("/tmp/stories")
            mock_page = {
                "id": "page_id_1",
                "properties": {
                    "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                    "Title": {"title": [{"plain_text": "Test Story"}]},
                    "Status": {"select": {"name": "IN_PROGRESS"}}
                }
            }
            sync.client.query_database.return_value = [mock_page]
            sync.client.retrieve_block_children.return_value = [] 
    
            # Mock File Ops with Conflict
            with patch.object(Path, "mkdir"), \
                 patch.object(Path, "write_text") as mock_write, \
                 patch.object(Path, "read_text", return_value="Local Content"), \
                 patch.object(Path, "exists", return_value=True): 
                 
                 mock_confirm.return_value = True # User chooses to overwrite
                 
                 sync.pull(artifact_type="story")
                 
                 mock_confirm.assert_called()
                 mock_write.assert_called()

    def test_pull_conflict_skip(self):
        with patch("agent.sync.notion.get_secret", return_value="fake_token"), \
             patch("agent.sync.notion.NotionClient") as MockClient, \
             patch("rich.prompt.Confirm.ask") as mock_confirm, \
             patch("agent.core.config.config") as mock_config:

            sync = NotionSync()
            sync.client = MockClient.return_value
            sync.state = {"Stories": "db_stories"}

            mock_config.stories_dir = Path("/tmp/stories")
            mock_page = {
                "id": "page_id_1",
                "properties": {
                    "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                    "Title": {"title": [{"plain_text": "Test Story"}]},
                    "Status": {"select": {"name": "IN_PROGRESS"}}
                }
            }
            sync.client.query_database.return_value = [mock_page]
            sync.client.retrieve_block_children.return_value = []
    
            # Mock File Ops with Conflict
            with patch.object(Path, "mkdir"), \
                 patch.object(Path, "write_text") as mock_write, \
                 patch.object(Path, "read_text", return_value="Different Local Content"), \
                 patch.object(Path, "exists", return_value=True): 
                 
                 mock_confirm.return_value = False # User chooses SKIP
                 
                 sync.pull(artifact_type="story")
                 
                 mock_confirm.assert_called()
                 mock_write.assert_not_called()
