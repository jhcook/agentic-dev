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
from pathlib import Path
import tempfile
import shutil
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
        
        # 3. Apply Fix (uses tempfile-based backup, not git stash)
        success = self.fixer.apply_fix(options[0], story_path)
        self.assertTrue(success)
        
        # Verify a backup was created
        file_str = str(story_path.resolve())
        self.assertIn(file_str, self.fixer._active_backups)
        
        # Verify file content was updated
        new_content = story_path.read_text()
        self.assertIn("## Impact Analysis Summary", new_content)
        
        # 4. Verify Fix — passing check clears backups
        def check_pass():
            return "## Impact Analysis Summary" in story_path.read_text()
            
        verified = self.fixer.verify_fix(check_pass)
        self.assertTrue(verified)
        # Backup should be cleared after successful verify
        self.assertEqual(len(self.fixer._active_backups), 0)

    def test_repair_rollback_on_failure(self):
        """
        Test that fix is rolled back if verification fails.
        """
        story_path = self.repo_root / "WEB-002-story.md"
        original_content = "Original Checksum"
        story_path.write_text(original_content)
        
        option = {"patched_content": "Corrupted Content"}
        
        # Apply fix (creates a real temp backup)
        self.fixer.apply_fix(option, story_path)
        
        # Confirm the file was modified
        self.assertEqual(story_path.read_text(), "Corrupted Content")
        
        # Verify - FAIL → should restore original content from backup
        def check_fail():
            return False
            
        verified = self.fixer.verify_fix(check_fail)
        
        self.assertFalse(verified)
        # File should be restored to original content
        self.assertEqual(story_path.read_text(), original_content)
        # Backups should be cleared
        self.assertEqual(len(self.fixer._active_backups), 0)

if __name__ == '__main__':
    unittest.main()

