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
    
    @patch("agent.sync.notion.get_secret")
    @patch("agent.sync.notion.NotionClient")
    @patch("rich.prompt.Confirm.ask")
    def setUp(self, mock_confirm, MockClient, mock_get_secret):
        mock_get_secret.return_value = "fake_token"
        mock_confirm.return_value = False # Default to No for safety
        self.sync = NotionSync()
        self.sync.state = {
            "Stories": "db_stories",
            "Plans": "db_plans", 
            "ADRs": "db_adrs"
        }

    @patch("agent.core.config.config")
    def test_pull_stories(self, mock_config):
        # Override state to only test Stories
        self.sync.state = {"Stories": "db_stories"}
        
        # Setup
        mock_config.stories_dir = Path("/tmp/stories")
        mock_page = {
            "id": "page_id_1",
            "properties": {
                "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                "Title": {"title": [{"plain_text": "Test Story"}]},
                "Status": {"select": {"name": "IN_PROGRESS"}}
            }
        }
        self.sync.client.query_database.return_value = [mock_page]
        
        # Mock block retrieval
        mock_block = {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "Content", "annotations": {"bold": False, "italic": False, "code": False}}]}
        }
        self.sync.client.retrieve_block_children.return_value = [mock_block]

        # Mock File Ops
        with patch.object(Path, "mkdir") as mock_mkdir, \
             patch.object(Path, "write_text") as mock_write, \
             patch.object(Path, "exists", return_value=False): # No conflict
            
             self.sync.pull()
             
             # Verify
             self.sync.client.query_database.assert_called_with("db_stories")
             mock_write.assert_called()
             # Verify content contains ID and Status
             args, _ = mock_write.call_args
             content = args[0]
             self.assertIn("# INFRA-054: Test Story", content)
             self.assertIn("## Status\nIN_PROGRESS", content)

    @patch("agent.core.config.config")
    @patch("rich.prompt.Confirm.ask")
    def test_pull_conflict_overwrite(self, mock_confirm, mock_config):
        # Setup
        mock_config.stories_dir = Path("/tmp/stories")
        mock_page = {
            "id": "page_id_1",
            "properties": {
                "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                "Title": {"title": [{"plain_text": "Test Story"}]},
                "Status": {"select": {"name": "IN_PROGRESS"}}
            }
        }
        self.sync.client.query_database.return_value = [mock_page]
        self.sync.client.retrieve_block_children.return_value = [] # Empty remote content vs local content

        # Mock File Ops with Conflict
        with patch.object(Path, "mkdir"), \
             patch.object(Path, "write_text") as mock_write, \
             patch.object(Path, "read_text", return_value="Local Content"), \
             patch.object(Path, "exists", return_value=True): 
             
             mock_confirm.return_value = True # User chooses to overwrite
             
             self.sync.pull()
             
             mock_confirm.assert_called()
             mock_write.assert_called()

    @patch("agent.core.config.config")
    @patch("rich.prompt.Confirm.ask")
    def test_pull_conflict_skip(self, mock_confirm, mock_config):
        # Setup
        mock_config.stories_dir = Path("/tmp/stories")
        mock_page = {
            "id": "page_id_1",
            "properties": {
                "ID": {"rich_text": [{"plain_text": "INFRA-054"}]},
                "Title": {"title": [{"plain_text": "Test Story"}]},
                "Status": {"select": {"name": "IN_PROGRESS"}}
            }
        }
        self.sync.client.query_database.return_value = [mock_page]
        self.sync.client.retrieve_block_children.return_value = []

        # Mock File Ops with Conflict
        with patch.object(Path, "mkdir"), \
             patch.object(Path, "write_text") as mock_write, \
             patch.object(Path, "read_text", return_value="Different Local Content"), \
             patch.object(Path, "exists", return_value=True): 
             
             mock_confirm.return_value = False # User chooses SKIP
             
             self.sync.pull()
             
             mock_confirm.assert_called()
             mock_write.assert_not_called()
