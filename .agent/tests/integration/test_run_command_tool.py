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
from unittest.mock import MagicMock

from agent.core.adk.tools import make_interactive_tools

class TestRunCommandTool(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_command_safe_execution(self):
        """Verify a safe command executes and streams output."""
        output_callback = MagicMock()
        tools = make_interactive_tools(self.repo_root, on_output=output_callback)
        run_command = next(t for t in tools if t.__name__ == 'run_command')

        # Create a file to be found by 'ls'
        (self.repo_root / "test_file.txt").touch()

        result = run_command("ls -l test_file.txt")
        self.assertIn("Command finished with exit code 0", result)
        
        # Verify output was streamed
        output_callback.assert_called()
        call_args_list = output_callback.call_args_list
        output_str = "\n".join([args[0][0] for args in call_args_list])
        self.assertIn("test_file.txt", output_str)

    def test_run_command_blocks_path_traversal(self):
        """Verify commands with '..' are blocked."""
        tools = make_interactive_tools(self.repo_root)
        run_command = next(t for t in tools if t.__name__ == 'run_command')

        result = run_command("ls ../")
        self.assertIn("path traversal ('..') is not allowed", result)

    def test_run_command_blocks_disallowed_absolute_path(self):
        """Verify commands with absolute paths outside the repo are blocked."""
        tools = make_interactive_tools(self.repo_root)
        run_command = next(t for t in tools if t.__name__ == 'run_command')

        result = run_command("ls /tmp")
        self.assertIn("Sandbox violation", result)
        self.assertIn("is outside the repository root", result)

    def test_run_command_empty_command(self):
        """Verify an empty command returns an error."""
        tools = make_interactive_tools(self.repo_root)
        run_command = next(t for t in tools if t.__name__ == 'run_command')

        result = run_command("   ")
        self.assertEqual("Error: empty command.", result)

if __name__ == '__main__':
    unittest.main()
