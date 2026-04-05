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
from pathlib import Path
import os
import sys

from backend.voice.tools.qa import run_backend_tests, shell_command

class TestToolsCWD(unittest.TestCase):
    """Verify that all voice tools pass repo_root as cwd= to subprocess calls.
    
    INFRA-183: repo_root is now a function parameter instead of agent_config global.
    """
    def setUp(self):
        self.mock_repo_root = Path("/mock/repo/root")

    @patch("backend.voice.tools.interactive_shell.ProcessLifecycleManager")
    @patch("backend.voice.tools.interactive_shell.EventBus")
    @patch("backend.voice.tools.interactive_shell.subprocess.Popen")
    @patch("backend.voice.tools.interactive_shell.get_session_id", return_value="test")
    def test_interactive_shell_cwd(self, mock_session, mock_popen, mock_event_bus, mock_plm):
        from backend.voice.tools.interactive_shell import start_interactive_shell
        
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        mock_plm.instance.return_value = MagicMock()
        
        with patch("backend.voice.tools.interactive_shell.threading.Thread"):
            result = start_interactive_shell("echo hello", repo_root=self.mock_repo_root)
            
        self.assertTrue(mock_popen.called, f"Popen should have been called. Tool output: {result}")
        call_args = mock_popen.call_args
        kwargs = call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch("backend.voice.tools.git.EventBus")
    @patch("backend.voice.tools.git.subprocess.run")
    @patch("backend.voice.tools.git.get_session_id", return_value="test")
    def test_get_git_status_cwd(self, mock_session, mock_run, mock_event_bus):
        from backend.voice.tools.git import get_git_status
        
        mock_run.return_value.stdout = "M file.txt"
        
        get_git_status(repo_root=self.mock_repo_root)
            
        self.assertTrue(mock_run.called, "subprocess.run should have been called")
        kwargs = mock_run.call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch("backend.voice.tools.git.EventBus")
    @patch("backend.voice.tools.git.subprocess.Popen")
    @patch("backend.voice.tools.git.subprocess.run")
    @patch("backend.voice.tools.git.get_session_id", return_value="test")
    def test_run_commit_cwd(self, mock_session, mock_run, mock_popen, mock_event_bus):
        from backend.voice.tools.git import run_commit
        
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""  # EOF
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        mock_run.return_value.stdout = "commit hash"
        
        run_commit(repo_root=self.mock_repo_root, message="test commit")
        
        self.assertTrue(mock_popen.called, "Popen should have been called")
        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    def test_run_backend_tests_cwd(self):
        with patch('backend.voice.tools.qa.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.readline.side_effect = ["Tests passed\n", ""]
            mock_process.stderr.readline.side_effect = [""]
            mock_process.stdout.close = MagicMock()
            mock_process.stderr.close = MagicMock()
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with patch('backend.voice.tools.qa.os.path.exists', return_value=True):
                run_backend_tests(repo_root=self.mock_repo_root, path="tests/")
            
            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.qa.get_session_id', return_value='test')
    def test_shell_command_cwd(self, mock_session):
        with patch('backend.voice.tools.qa.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.readline.return_value = ""
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=MagicMock()):
                with patch('backend.voice.events.EventBus.publish'):
                    shell_command(command="ls", repo_root=self.mock_repo_root, cwd=".")
            
            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.qa.subprocess.Popen')
    @patch('backend.voice.tools.qa.get_session_id', return_value='test')
    def test_shell_command_cwd_verified(self, mock_session, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=MagicMock()):
            with patch('backend.voice.events.EventBus.publish'):
                shell_command(command="ls", repo_root=self.mock_repo_root, cwd=".")
        
        args, kwargs = mock_popen.call_args
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.workflows.get_session_id', return_value='test')
    def test_run_new_story_cwd(self, mock_session):
        from backend.voice.tools.workflows import run_new_story
        
        with patch('backend.voice.tools.workflows.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.readline.side_effect = ["", ""]
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=MagicMock()):
                with patch('backend.voice.events.EventBus.publish'):
                    run_new_story(repo_root=self.mock_repo_root)
            
            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.fix_story.get_session_id', return_value='test')
    def test_fix_story_cwd(self, mock_session):
        from backend.voice.tools.fix_story import interactive_fix_story
        
        mock_file = MagicMock()
        mock_file.name = "WEB-001-story.md"
        mock_file.__str__.return_value = "/path/to/WEB-001-story.md"
        
        with patch.object(Path, 'rglob', return_value=[mock_file]):
            with patch('backend.voice.tools.fix_story.subprocess.Popen') as mock_popen, \
                 patch('backend.voice.tools.fix_story.os.path.exists', return_value=True):
                mock_process = MagicMock()
                mock_process.communicate.return_value = ("Story validation passed", "")
                mock_process.returncode = 0
                mock_popen.return_value = mock_process
                
                with patch('backend.voice.events.EventBus.publish'):
                    interactive_fix_story("WEB-001", repo_root=self.mock_repo_root)
                
                args, kwargs = mock_popen.call_args
                self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    def test_get_recent_logs_cwd(self):
        from backend.voice.tools.observability import get_recent_logs
        
        # Create mock path that supports / operator
        mock_log_path = MagicMock()
        mock_log_path.exists.return_value = True
        mock_log_path.__str__.return_value = str(self.mock_repo_root / "agent.log")
        
        with patch.object(Path, '__truediv__', return_value=mock_log_path):
            with patch('backend.voice.tools.observability.subprocess.run') as mock_run:
                mock_run.return_value.stdout = "logs"
                
                get_recent_logs(repo_root=self.mock_repo_root)
                    
                args, kwargs = mock_run.call_args
                self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

if __name__ == "__main__":
    unittest.main()
