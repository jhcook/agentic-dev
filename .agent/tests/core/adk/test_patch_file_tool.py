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
from pathlib import Path
from tempfile import TemporaryDirectory

from agent.core.adk.tools import patch_file

class TestPatchFileTool(unittest.TestCase):
    def test_patch_file_success(self):
        with TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir)
            file_path = temp_path / "test_file.txt"
            
            # Create a file with initial content
            initial_content = "Hello world\nThis is a test\nGoodbye world"
            with open(file_path, "w") as f:
                f.write(initial_content)
                
            # Use the patch_file tool to replace a line
            search_str = "This is a test"
            replace_str = "This is a successful patch"
            patch_file(path=str(file_path), search=search_str, replace=replace_str)
            
            # Verify the content was updated
            with open(file_path, "r") as f:
                content = f.read()
                
            expected_content = "Hello world\nThis is a successful patch\nGoodbye world"
            self.assertEqual(content, expected_content)

    def test_patch_file_no_match(self):
        with TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir)
            file_path = temp_path / "test_file.txt"
            
            initial_content = "Hello world\nThis is a test\nGoodbye world"
            with open(file_path, "w") as f:
                f.write(initial_content)
                
            # Attempt to patch with a search string that doesn't exist
            with self.assertRaises(ValueError) as cm:
                patch_file(path=str(file_path), search="nonexistent string", replace="wont work")
            
            self.assertIn("Search string 'nonexistent string' not found or found multiple times in", str(cm.exception))
            
            # Verify the content was not changed
            with open(file_path, "r") as f:
                content = f.read()
            self.assertEqual(content, initial_content)

    def test_patch_file_multiple_matches(self):
        with TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir)
            file_path = temp_path / "test_file.txt"
            
            # Create a file with a repeated line
            initial_content = "Hello world\nThis is a test\nThis is a test\nGoodbye world"
            with open(file_path, "w") as f:
                f.write(initial_content)
                
            # Attempt to patch with a search string that appears multiple times
            with self.assertRaises(ValueError) as cm:
                patch_file(path=str(file_path), search="This is a test", replace="wont work")
            
            self.assertIn("Search string 'This is a test' not found or found multiple times in", str(cm.exception))
            
            # Verify the content was not changed
            with open(file_path, "r") as f:
                content = f.read()
            self.assertEqual(content, initial_content)

if __name__ == '__main__':
    unittest.main()
