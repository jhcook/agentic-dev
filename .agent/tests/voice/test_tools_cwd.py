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

# Ensure we can import from src
sys.path.append(os.path.abspath(".agent/src"))

from backend.voice.tools.qa import run_backend_tests, shell_command

class TestToolsCWD(unittest.TestCase):
    def setUp(self):
        self.mock_repo_root = Path("/mock/repo/root")
        self.config = {"configurable": {"thread_id": "test_thread"}}

    @patch("backend.voice.tools.interactive_shell.ProcessLifecycleManager")
    @patch("backend.voice.tools.interactive_shell.EventBus")
    @patch("backend.voice.tools.interactive_shell.subprocess.Popen")
    @patch("backend.voice.tools.interactive_shell.agent_config")
    def test_interactive_shell_cwd(self, mock_config, mock_popen, mock_event_bus, mock_plm):
        from backend.voice.tools.interactive_shell import start_interactive_shell
        
        mock_config.repo_root = self.mock_repo_root
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Mock PLM instance
        mock_plm.instance.return_value = MagicMock()
        
        if hasattr(start_interactive_shell, "func"):
            result = start_interactive_shell.func("echo hello", config={"configurable": {"thread_id": "test"}})
        else:
            result = start_interactive_shell("echo hello")
            
        print(f"Result: {result}")
        self.assertTrue(mock_popen.called, f"Popen should have been called. Tool output: {result}")
        call_args = mock_popen.call_args
        # Popen args are (command, ... cwd=...)
        kwargs = call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch("backend.voice.tools.git.EventBus")
    @patch("backend.voice.tools.git.subprocess.run")
    @patch("backend.voice.tools.git.agent_config")
    def test_get_git_status_cwd(self, mock_config, mock_run, mock_event_bus):
        from backend.voice.tools.git import get_git_status
        
        mock_config.repo_root = self.mock_repo_root
        mock_run.return_value.stdout = "M file.txt"
        
        if hasattr(get_git_status, "func"):
            get_git_status.func(config={"configurable": {"thread_id": "test"}})
        else:
            get_git_status()
            
        self.assertTrue(mock_run.called, "subprocess.run should have been called")
        kwargs = mock_run.call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch("backend.voice.tools.git.EventBus")
    @patch("backend.voice.tools.git.subprocess.Popen")
    @patch("backend.voice.tools.git.subprocess.run")
    @patch("backend.voice.tools.git.agent_config")
    def test_run_commit_cwd(self, mock_config, mock_run, mock_popen, mock_event_bus):
        from backend.voice.tools.git import run_commit
        
        mock_config.repo_root = self.mock_repo_root
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = "" # EOF
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        mock_run.return_value.stdout = "commit hash"
        
        if hasattr(run_commit, "func"):
            run_commit.func(message="test commit", config={"configurable": {"thread_id": "test"}})
        else:
            run_commit(message="test commit")
        
        self.assertTrue(mock_popen.called, "Popen should have been called")
        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch("backend.voice.tools.project.glob.glob")
    @patch("backend.voice.tools.project.config")
    def test_list_stories_cwd(self, mock_config, mock_glob):
        from backend.voice.tools.project import list_stories
        
        mock_config.repo_root = self.mock_repo_root
        mock_glob.return_value = []
        
        if hasattr(list_stories, "func"):
            list_stories.func()
        else:
            list_stories()
            
        # Verify that glob was called with an absolute path starting with repo_root
        args, _ = mock_glob.call_args
        pattern = args[0]
        # We expect something like /mock/repo/root/.agent/cache/stories/**/*.md
        # If it's relative, this assertion will fail, catching the bug.
        self.assertTrue(str(pattern).startswith(str(self.mock_repo_root)), 
                        f"Glob pattern '{pattern}' should use absolute path from repo_root")

    @patch("backend.voice.tools.project.glob.glob")
    @patch("backend.voice.tools.project.config")
    def test_list_runbooks_cwd(self, mock_config, mock_glob):
        from backend.voice.tools.project import list_runbooks
        
        mock_config.repo_root = self.mock_repo_root
        mock_glob.return_value = []
        
        if hasattr(list_runbooks, "func"):
            list_runbooks.func()
        else:
            list_runbooks()
            
        args, _ = mock_glob.call_args
        pattern = args[0]
        self.assertTrue(str(pattern).startswith(str(self.mock_repo_root)),
                        f"Glob pattern '{pattern}' should use absolute path from repo_root")

    @patch('backend.voice.tools.qa.agent_config')
    def test_run_backend_tests_cwd(self, mock_config):
        mock_config.repo_root = self.mock_repo_root
        
        # Mock subprocess — run_backend_tests uses Popen, not subprocess.run
        with patch('backend.voice.tools.qa.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.readline.side_effect = ["Tests passed\n", ""]
            mock_process.stderr.readline.side_effect = [""]
            mock_process.stdout.close = MagicMock()
            mock_process.stderr.close = MagicMock()
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            # Need to patch os.path.exists to pass validation
            with patch('backend.voice.tools.qa.os.path.exists', return_value=True):
                if hasattr(run_backend_tests, "func"):
                    run_backend_tests.func(path="tests/")
                else:
                    run_backend_tests(path="tests/")
            
            # Verify call
            args, kwargs = mock_popen.call_args
            assert kwargs.get("cwd") == str(mock_config.repo_root)

    @patch('backend.voice.tools.qa.agent_config')
    def test_shell_command_cwd(self, mock_config):
        mock_config.repo_root = self.mock_repo_root
        
        # Mock LifecycleManager to avoid registration errors
        mock_manager = MagicMock()
        with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=mock_manager):
            # Mock EventBus
            with patch('backend.voice.events.EventBus.publish'):
                # Run tool
                # Need to patch os.getcwd for validation
                with patch('os.getcwd', return_value=str(self.mock_repo_root)):
                     if hasattr(shell_command, "func"):
                         shell_command.func(command="ls", cwd=".", config=self.config)
                     else:
                         shell_command(command="ls", cwd=".", config=self.config)
                
                # Verify Popen called with correct cwd
                # subprocess.Popen is patched globally? No, imports are tricky.
                # shell_command uses subprocess.Popen directly.
                # We need to patch subprocess within qa.py context or generally.
                # Just assume success if we can patch it.
                pass 
                # Actually, wait. We need to patch Popen in the tool module to verify kwargs
                
    @patch('backend.voice.tools.qa.subprocess.Popen')
    @patch('backend.voice.tools.qa.agent_config')
    def test_shell_command_cwd_verified(self, mock_config, mock_popen):
        mock_config.repo_root = self.mock_repo_root
        
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        mock_manager = MagicMock()
        with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=mock_manager):
             with patch('backend.voice.events.EventBus.publish'):
                with patch('os.getcwd', return_value=str(self.mock_repo_root)):
                     shell_command.func(command="ls", cwd=".", config=self.config)
        
        args, kwargs = mock_popen.call_args
        self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))


    @patch('backend.voice.tools.workflows.agent_config')
    def test_run_new_story_cwd(self, mock_config):
        from backend.voice.tools.workflows import run_new_story
        mock_config.repo_root = self.mock_repo_root
        
        with patch('backend.voice.tools.workflows.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            # Side effect to ensure 'iter' finishes immediately
            mock_process.stdout.readline.side_effect = ["", ""]
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with patch('backend.voice.process_manager.ProcessLifecycleManager.instance', return_value=MagicMock()):
                with patch('backend.voice.events.EventBus.publish'):
                     if hasattr(run_new_story, "func"):
                         run_new_story.func(config=self.config)
                     else:
                         run_new_story()
            
            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.fix_story.agent_config')
    def test_fix_story_cwd(self, mock_config):
        from backend.voice.tools.fix_story import interactive_fix_story
        mock_config.repo_root = self.mock_repo_root
        
        # Mock stories_dir.rglob to return a fake file path
        mock_file = MagicMock()
        mock_file.name = "WEB-001-story.md"
        mock_file.__str__.return_value = "/path/to/WEB-001-story.md"
        mock_config.stories_dir.rglob.return_value = [mock_file]
        
        with patch('backend.voice.tools.fix_story.subprocess.Popen') as mock_popen, \
             patch('backend.voice.tools.fix_story.os.path.exists', return_value=True):
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("Story validation passed", "")
            mock_process.returncode = 0
            mock_popen.return_value = mock_process
            
            with patch('backend.voice.events.EventBus.publish'):
                if hasattr(interactive_fix_story, "func"):
                    interactive_fix_story.func(story_id="WEB-001", config=self.config)
                else:
                    interactive_fix_story("WEB-001")
            
            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

    @patch('backend.voice.tools.observability.agent_config')
    def test_get_recent_logs_cwd(self, mock_config):
        from backend.voice.tools.observability import get_recent_logs
        
        # Use a MagicMock for repo_root so we can mock __truediv__
        mock_root = MagicMock()
        mock_root.__str__.return_value = str(self.mock_repo_root)
        mock_config.repo_root = mock_root
        
        # When (repo_root / "x") is called, return a mock path
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = True
        mock_path_obj.__str__.return_value = str(self.mock_repo_root / "agent.log")
        mock_root.__truediv__.return_value = mock_path_obj
        
        with patch('backend.voice.tools.observability.subprocess.run') as mock_run:
            mock_run.return_value.stdout = "logs"
            
            if hasattr(get_recent_logs, "func"):
                get_recent_logs.func()
            else:
                get_recent_logs()
                
            args, kwargs = mock_run.call_args
            # Verify cwd is the string of our repo root mock
            self.assertEqual(kwargs.get("cwd"), str(self.mock_repo_root))

if __name__ == "__main__":
    unittest.main()
