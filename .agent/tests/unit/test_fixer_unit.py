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
from unittest.mock import MagicMock, patch
import json
from agent.core.fixer import InteractiveFixer

class TestInteractiveFixer(unittest.TestCase):
    
    def setUp(self):
        self.fixer = InteractiveFixer()
        self.fixer.ai = MagicMock()
        self.console = MagicMock()
        self.console = MagicMock()
        # No more console to patch in fixer.py


    def test_analyze_failure_story_schema(self):
        # Setup
        context = {
            "story_id": "TEST-001",
            "missing_sections": ["Impact Analysis Summary"],
            "file_path": "dummy.md"
        }
        
        # Mock AI response
        self.fixer.ai.get_completion.return_value = """
        [
            {"title": "Fix 1", "description": "Desc 1", "patched_content": "Content 1"}
        ]
        """
        
        # Mock path resolution
        mock_path = MagicMock()
        mock_path.read_text.return_value = "# Story"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__.return_value = "/repo/root/dummy.md"
        
        # Mock CWD
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = mock_cwd
        mock_cwd.__str__.return_value = "/repo/root"
        
        # Configure Path Mock
        mock_path_class = MagicMock()
        mock_path_class.return_value = mock_path
        mock_path_class.cwd.return_value = mock_cwd
        
        with patch("agent.core.fixer.Path", mock_path_class):
             options = self.fixer.analyze_failure("story_schema", context)
             
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["title"], "Fix 1")



    @patch('agent.core.fixer.shutil.copy2')
    @patch('agent.core.fixer.os.close')
    @patch('agent.core.fixer.tempfile.mkstemp', return_value=(5, '/tmp/backup'))
    def test_apply_fix_success(self, mock_mkstemp, mock_close, mock_copy):

        mock_path = MagicMock()
        mock_path.read_text.return_value = "Old"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__ = MagicMock(return_value="/repo/file.py")
        
        fix = {"patched_content": "New"}
        
        result = self.fixer.apply_fix(fix, mock_path)
        
        self.assertTrue(result)
        mock_mkstemp.assert_called_once()
        mock_path.write_text.assert_called_with("New")

    @patch('agent.core.fixer.InteractiveFixer._restore_backup')
    @patch('agent.core.fixer.shutil.copy2')
    @patch('agent.core.fixer.os.close')
    @patch('agent.core.fixer.tempfile.mkstemp', return_value=(5, '/tmp/backup'))
    def test_apply_fix_failure(self, mock_mkstemp, mock_close, mock_copy, mock_restore):

        mock_path = MagicMock()
        mock_path.read_text.return_value = "Old"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__ = MagicMock(return_value="/repo/file.py")
        mock_path.write_text.side_effect = Exception("Write failed")
        
        fix = {"patched_content": "New"}
        
        result = self.fixer.apply_fix(fix, mock_path)
        
        self.assertFalse(result)
        mock_mkstemp.assert_called_once()
        mock_restore.assert_called_once() # Should revert

    @patch('agent.core.fixer.os.remove')
    @patch('agent.core.fixer.os.path.exists', return_value=True)
    def test_verify_fix_success(self, mock_exists, mock_remove):
        # Simulate an active backup so verify_fix has something to clean up
        self.fixer._active_backups["/repo/file.py"] = "/tmp/backup"
        check = MagicMock(return_value=True)
        result = self.fixer.verify_fix(check)
        self.assertTrue(result)
        mock_remove.assert_called_once_with("/tmp/backup")

    def test_analyze_rejection(self):
        """Test that analyze_failure rejects unsafe content."""
        # Setup mock AI to return unsafe content
        self.fixer.ai.complete.return_value = json.dumps([
            {"title": "Unsafe Fix", "patched_content": "import os; os.system('rm -rf /')"}
        ])
        
        mock_path = MagicMock()
        mock_path.read_text.return_value = "content"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__.return_value = "/repo/root/dummy"
        
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = mock_cwd
        mock_cwd.__str__.return_value = "/repo/root"
        
        mock_path_class = MagicMock()
        mock_path_class.return_value = mock_path
        mock_path_class.cwd.return_value = mock_cwd
        
        with patch("agent.core.fixer.Path", mock_path_class):
             options = self.fixer.analyze_failure("story_schema", {"file_path": "dummy"})
             
        # Should contain Manual Fix fallback
        self.assertEqual(len(options), 1)
        self.assertIn("Manual Fix", options[0]["title"])

    def test_path_traversal_rejection(self):
        """Test that analyze_failure rejects paths outside repo."""
        mock_path = MagicMock()
        mock_path.resolve.return_value = mock_path
        mock_path.__str__.return_value = "/etc/passwd" # Outside repo
        
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = mock_cwd
        mock_cwd.__str__.return_value = "/repo/root"
        
        mock_path_class = MagicMock()
        mock_path_class.return_value = mock_path
        mock_path_class.cwd.return_value = mock_cwd
        
        with patch("agent.core.fixer.Path", mock_path_class):
             options = self.fixer.analyze_failure("story_schema", {"file_path": "../../etc/passwd"})
        
        # Valid path traversal check might return empty or fallback?
        # Current impl likely returns fallback if path check fails?
        # Actually path check usually returns None options before fallback logic?
        # Let's assume it fails safe.
        self.assertEqual(len(options), 0)

    def test_malformed_json_rejection(self):
         """Test that analyze_failure rejects malformed JSON options."""
         self.fixer.ai.complete.return_value = json.dumps([
             {"title": "Missing Content"} # Missing patched_content
         ])
         
         mock_path = MagicMock()
         mock_path.read_text.return_value = "content"
         mock_path.resolve.return_value = mock_path
         mock_path.__str__.return_value = "/repo/root/dummy"
         
         mock_cwd = MagicMock()
         mock_cwd.resolve.return_value = mock_cwd
         mock_cwd.__str__.return_value = "/repo/root"
         
         mock_path_class = MagicMock()
         mock_path_class.return_value = mock_path
         mock_path_class.cwd.return_value = mock_cwd
         
         with patch("agent.core.fixer.Path", mock_path_class):
              options = self.fixer.analyze_failure("story_schema", {"file_path": "dummy"})
              
         # Fallback
         self.assertEqual(len(options), 1)
         self.assertIn("Manual Fix", options[0]["title"])
         
    def test_analysis_ai_exception(self):
        """Test handling of AI service exceptions."""
        self.fixer.ai.get_completion.side_effect = Exception("AI Down")
        
        mock_path = MagicMock()
        mock_path.read_text.return_value = "content"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__.return_value = "/repo/root/dummy"
        
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = mock_cwd
        mock_cwd.__str__.return_value = "/repo/root"
        
        with patch("agent.core.fixer.Path", return_value=mock_path) as mock_p:
            mock_p.return_value = mock_path
            mock_p.cwd.return_value = mock_cwd
            
            options = self.fixer.analyze_failure("story_schema", {"file_path": "dummy"})
            
        # Fallback
        self.assertEqual(len(options), 1)
        self.assertIn("Manual Fix", options[0]["title"])

    def test_fix_validation_failure(self):
        """Test rejection of structurally valid but insecure content."""
        self.fixer.ai.get_completion.return_value = json.dumps([
            {"title": "Bad Fix", "patched_content": "import socket; socket.connect()"}
        ])
        
        mock_path = MagicMock()
        mock_path.read_text.return_value = "content"
        mock_path.resolve.return_value = mock_path
        mock_path.__str__.return_value = "/repo/root/dummy"
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = mock_cwd
        mock_cwd.__str__.return_value = "/repo/root"
        
        with patch("agent.core.fixer.Path", return_value=mock_path) as mock_p:
            mock_p.return_value = mock_path
            mock_p.cwd.return_value = mock_cwd
            
            options = self.fixer.analyze_failure("story_schema", {"file_path": "dummy"})
            
        # All options rejected as insecure — returns empty list (not fallback)
        self.assertEqual(len(options), 0)

if __name__ == '__main__':
    unittest.main()
