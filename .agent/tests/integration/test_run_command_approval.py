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
from unittest.mock import patch, MagicMock

from agent.core.adk.tools import make_interactive_tools

# run_command is a nested function inside make_interactive_tools
_tools = make_interactive_tools(Path("."))
run_command = next(t for t in _tools if t.__name__ == "run_command")


class TestRunCommandApproval(unittest.TestCase):

    @patch('subprocess.Popen')
    def test_run_command_executes(self, mock_popen):
        """Verify run_command executes and returns output."""
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['Success\n', '']
        mock_proc.poll.side_effect = [None, 0, 0]
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        result = run_command(command='echo hello')
        self.assertIn('Success', result)

    def test_run_command_empty(self):
        """Verify run_command rejects empty commands."""
        result = run_command(command='')
        self.assertIn('Error', result)

    def test_run_command_path_traversal(self):
        """Verify run_command rejects path traversal."""
        result = run_command(command='cat ../../etc/passwd')
        self.assertIn('Error', result)


if __name__ == '__main__':
    unittest.main()

