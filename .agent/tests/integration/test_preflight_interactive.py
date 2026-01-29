
import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path
import tempfile
import shutil
import os
from agent.core.fixer import InteractiveFixer

class TestPreflightInteractiveIntegration(unittest.TestCase):
    """
    Integration tests for the Interactive Preflight Repair flow.
    Simulates the end-to-end process of analyzing a failure, generating a fix, and applying it.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.test_dir)
        self.fixer = InteractiveFixer()
        
        # Mock AI service to return predictable fixes
        self.fixer.ai = MagicMock()
        
        # Patch Path.cwd to return our temp dir
        self.cwd_patcher = patch('pathlib.Path.cwd', return_value=self.repo_root)
        self.mock_cwd = self.cwd_patcher.start()
        
    def tearDown(self):
        self.cwd_patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_full_repair_flow(self):
        """
        Test the complete flow: Corrupt Story -> Analyze -> Fix -> Verify
        """
        # 1. Setup: Create a corrupted story (missing "Impact Analysis Summary")
        story_path = self.repo_root / "WEB-001-story.md"
        content = """# Story WEB-001
## Problem Statement
Problem.
## User Story
As a user...
## Acceptance Criteria
- AC1
## Non-Functional Requirements
- NFR1
## Test Strategy
- TS1
## Rollback Plan
- RB1
"""
        story_path.write_text(content)
        
        # 2. Analyze Failure
        context = {
            "story_id": "WEB-001",
            "missing_sections": ["Impact Analysis Summary"],
            "file_path": str(story_path)
        }
        
        # Mock AI response with a valid fix
        fix_content = content + "\n## Impact Analysis Summary\nNone."
        ai_response = json.dumps([
            {
                "title": "Add Impact Analysis",
                "description": "Adds the missing section.",
                "patched_content": fix_content
            }
        ])
        self.fixer.ai.get_completion.return_value = ai_response
        
        # Run Analysis
        options = self.fixer.analyze_failure("story_schema", context)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["title"], "Add Impact Analysis")
        
        # 3. Apply Fix
        # In a real integration, we'd mock the git stash calls to avoid messing with actual git if running locally
        # But this is a temp dir, so git commands might fail if it's not a git repo.
        # We should mock git stash for this test.
        with patch.object(self.fixer, '_git_stash_save') as mock_save, \
             patch.object(self.fixer, '_git_stash_pop') as mock_pop, \
             patch.object(self.fixer, '_git_stash_drop') as mock_drop:
             
            success = self.fixer.apply_fix(options[0], story_path)
            self.assertTrue(success)
            mock_save.assert_called_once()
            
            # Verify file content
            new_content = story_path.read_text()
            self.assertIn("## Impact Analysis Summary", new_content)
            
            # 4. Verify Fix
            # Simulate a passing check
            def check_pass():
                return "## Impact Analysis Summary" in story_path.read_text()
                
            verified = self.fixer.verify_fix(check_pass)
            self.assertTrue(verified)
            mock_drop.assert_called_once() # Stash should be dropped

    def test_repair_rollback_on_failure(self):
        """
        Test that fix is rolled back if verification fails.
        """
        story_path = self.repo_root / "WEB-002-story.md"
        story_path.write_text("Original Checksum")
        
        option = {"patched_content": "Corrupted Content"}
        
        # We need to simulate the revert (pop) actually restoring content
        # since we are mocking the git command, we must simulate the effect manually or check the call
        
        with patch.object(self.fixer, '_git_stash_save'), \
             patch.object(self.fixer, '_git_stash_pop') as mock_pop, \
             patch.object(self.fixer, '_git_stash_drop'):
             
             # Apply
             self.fixer.apply_fix(option, story_path)
             
             # Verify - FAIL
             def check_fail():
                 return False
                 
             verified = self.fixer.verify_fix(check_fail)
             
             self.assertFalse(verified)
             mock_pop.assert_called_once()
             
             # Note: In a real git repo, pop would restore. Here we just assert pop was called.

if __name__ == '__main__':
    unittest.main()
