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
from unittest.mock import patch, MagicMock

from agent.core.adk.tools import run_command
from agent.core.adk.runtime import get_user_consent

class TestRunCommandApproval(unittest.TestCase):

    @patch('agent.core.adk.runtime.get_user_consent')
    @patch('subprocess.run')
    def test_run_command_approved(self, mock_subprocess_run, mock_get_user_consent):
        """Verify run_command executes when user provides consent."""
        # Arrange: Simulate user approving the command
        mock_get_user_consent.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'Success'
        mock_proc.stderr = ''
        mock_subprocess_run.return_value = mock_proc

        command_to_run = 'ls -l'

        # Act: Execute the tool
        result = run_command(command=command_to_run)

        # Assert: The consent function was called and the command was executed
        mock_get_user_consent.assert_called_once_with(f'Permit execution of: "{command_to_run}"?')
        mock_subprocess_run.assert_called_once_with(command_to_run, shell=True, capture_output=True, text=True, check=False)
        self.assertIn('Success', result)

    @patch('agent.core.adk.runtime.get_user_consent')
    @patch('subprocess.run')
    def test_run_command_denied(self, mock_subprocess_run, mock_get_user_consent):
        """Verify run_command does NOT execute when user denies consent."""
        # Arrange: Simulate user denying the command
        mock_get_user_consent.return_value = False
        command_to_run = 'rm -rf /'

        # Act & Assert: The tool should raise a PermissionError
        with self.assertRaises(PermissionError) as cm:
            run_command(command=command_to_run)
        
        self.assertEqual(str(cm.exception), 'User denied execution of command.')

        # Assert: The consent function was called but the command was NOT executed
        mock_get_user_consent.assert_called_once_with(f'Permit execution of: "{command_to_run}"?')
        mock_subprocess_run.assert_not_called()

if __name__ == '__main__':
    unittest.main()
