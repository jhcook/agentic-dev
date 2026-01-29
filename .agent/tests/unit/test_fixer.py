
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



    @patch('agent.core.fixer.InteractiveFixer._git_stash_save')
    @patch('agent.core.fixer.InteractiveFixer._git_stash_pop')
    def test_apply_fix_success(self, mock_pop, mock_save):

        mock_path = MagicMock()
        mock_path.read_text.return_value = "Old"
        
        fix = {"patched_content": "New"}
        
        result = self.fixer.apply_fix(fix, mock_path)
        
        self.assertTrue(result)
        mock_save.assert_called_once()
        mock_path.write_text.assert_called_with("New")
        mock_pop.assert_not_called()

    @patch('agent.core.fixer.InteractiveFixer._git_stash_save')
    @patch('agent.core.fixer.InteractiveFixer._git_stash_pop')
    def test_apply_fix_failure(self, mock_pop, mock_save):

        mock_path = MagicMock()
        mock_path.read_text.return_value = "Old"
        mock_path.write_text.side_effect = Exception("Write failed")
        
        fix = {"patched_content": "New"}
        
        result = self.fixer.apply_fix(fix, mock_path)
        
        self.assertFalse(result)
        mock_save.assert_called_once()
        mock_pop.assert_called_once() # Should revert

    @patch('agent.core.fixer.InteractiveFixer._git_stash_drop')
    def test_verify_fix_success(self, mock_drop):
        check = MagicMock(return_value=True)
        result = self.fixer.verify_fix(check)
        self.assertTrue(result)
        mock_drop.assert_called_once() # Should drop stash




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
             
        # Should be empty because it contained 'import os'
        self.assertEqual(len(options), 0)



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
              
         self.assertEqual(len(options), 0)
         
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
            
        self.assertEqual(len(options), 0)

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
            
        self.assertEqual(len(options), 0)

if __name__ == '__main__':
    unittest.main()
