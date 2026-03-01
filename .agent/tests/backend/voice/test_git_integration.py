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

import pytest
from unittest.mock import MagicMock, patch
from backend.voice.tools.git import get_git_status, get_git_diff

@pytest.fixture
def mock_subprocess_run():
    with patch('subprocess.run') as mock:
        yield mock

@pytest.fixture
def mock_event_bus():
    with patch('backend.voice.tools.git.EventBus') as mock:
        yield mock

def test_git_status_streaming(mock_subprocess_run, mock_event_bus):
    """Test that git status publishes output to EventBus."""
    
    mock_subprocess_run.return_value.stdout = "?? untracked.txt\n"
    mock_subprocess_run.return_value.returncode = 0
    
    config = {"configurable": {"thread_id": "session-1"}}
    
    result = get_git_status.func(config=config)
    
    # Check output format
    import json
    data = json.loads(result)
    assert "untracked.txt" in data["untracked"]
    
    # Check streaming
    mock_event_bus.publish.assert_called_once()
    args = mock_event_bus.publish.call_args[0]
    assert args[0] == "session-1" # Session ID
    assert args[1] == "console"
    assert "=== Git Status (JSON) ===" in args[2]

def test_git_diff_streaming_truncation(mock_subprocess_run, mock_event_bus):
    """Test that large git diffs are truncated and streamed."""
    
    # Create large output > 5000 chars
    large_diff = "a" * 6000
    mock_subprocess_run.return_value.stdout = large_diff
    mock_subprocess_run.return_value.returncode = 0
    
    config = {"configurable": {"thread_id": "session-1"}}
    
    result = get_git_diff.func(config=config)
    
    # Check truncation return
    assert len(result) < 5100
    assert "...[Truncated]" in result
    
    mock_event_bus.publish.assert_called_once()
    args = mock_event_bus.publish.call_args[0]
    assert len(args[2]) >= 6000 # Should stream full content

def test_git_push_upstream_handling(mock_event_bus):
    """Test that git_push_branch handles missing upstream automatically."""
    from backend.voice.tools.git import git_push_branch
    
    with patch('subprocess.Popen') as mock_popen, \
         patch('subprocess.run') as mock_run:
        
        # Setup Pass 1: First push fails with "no upstream"
        proc1 = MagicMock()
        proc1.communicate.return_value = ("", "fatal: The current branch feature/test has no upstream branch.")
        proc1.returncode = 128
        
        # Setup Pass 2: Retry with --set-upstream
        proc2 = MagicMock()
        proc2.communicate.return_value = ("Branch 'feature/test' set up to track remote branch...", "")
        proc2.returncode = 0
        
        mock_popen.side_effect = [proc1, proc2]
        
        # Branch check mock
        mock_run.return_value.stdout = "feature/test"
        mock_run.return_value.returncode = 0
        
        config = {"configurable": {"thread_id": "session-push"}}
        
        # Run
        result = git_push_branch.func(config=config)
        
        # Verify
        assert "Successfully pushed and set upstream" in result
        assert "feature/test" in result
        
        # Verify 2 popen calls
        assert mock_popen.call_count == 2
        # First call: git push
        assert mock_popen.call_args_list[0][0][0] == ["git", "push"]
        # First call: git push
        assert mock_popen.call_args_list[0][0][0] == ["git", "push"]
        # Second call: git push --set-upstream origin feature/test
        assert mock_popen.call_args_list[1][0][0] == ["git", "push", "--set-upstream", "origin", "feature/test"]

def test_run_pr_opens_url(mock_event_bus):
    """Test that run_pr emits open_url event when URL is found."""
    from backend.voice.tools.git import run_pr
    
    with patch('subprocess.Popen') as mock_popen, \
         patch('backend.voice.process_manager.ProcessLifecycleManager') as mock_plm:
         
        # Ensure instance().register/unregister works
        mock_plm.instance.return_value = MagicMock()
        
        # Setup Pass 1: Date (subprocess.check_output uses context manager)
        proc_date = MagicMock()
        proc_date.communicate.return_value = (b"1700000000\n", b"")
        proc_date.returncode = 0
        proc_date.poll.return_value = 0
        proc_date.__enter__.return_value = proc_date
        
        # Setup Pass 2: Push (git push)
        proc_push = MagicMock()
        proc_push.communicate.return_value = ("Everything up-to-date", "")
        proc_push.returncode = 0
        proc_push.poll.return_value = 0
        
        # Setup Pass 3: PR (agent pr)
        proc_pr = MagicMock()
        proc_pr.stdout.readline.side_effect = [
            "Creating PR...\n", 
            "https://github.com/org/repo/pull/42\n", 
            ""
        ]
        proc_pr.communicate.return_value = (None, None) 
        proc_pr.returncode = 0
        proc_pr.poll.return_value = 0
        proc_pr.wait.return_value = 0
        
        mock_popen.side_effect = [proc_date, proc_push, proc_pr]
        
        config = {"configurable": {"thread_id": "session-pr"}}
        
        result = run_pr.func(config=config)
        
        assert "PR creation started" in result
        
        # Wait for thread
        import time
        time.sleep(0.2)
        
        # Verify calls
        assert mock_popen.call_count == 3
        
        # 1. Date
        assert "date" in mock_popen.call_args_list[0][0][0]
        
        # 2. Push
        assert mock_popen.call_args_list[1][0][0] == ["git", "push"]
        
        # 3. PR
        cmd = mock_popen.call_args_list[2][0][0]
        assert "agent pr" in cmd
        
        # 3. Open URL event
        open_url_calls = [
            call for call in mock_event_bus.publish.call_args_list 
            if call[0][1] == "open_url"
        ]
        assert len(open_url_calls) == 1
        assert open_url_calls[0][0][2] == {"url": "https://github.com/org/repo/pull/42"}

def test_run_commit_streaming(mock_event_bus):
    """Test that run_commit streams output to EventBus."""
    from backend.voice.tools.git import run_commit
    
    # Mock Popen
    with patch('subprocess.Popen') as mock_popen, \
         patch('subprocess.run') as mock_run:
        
        # Setup Pass 1: Commit Process
        process_mock = MagicMock()
        process_mock.stdout.readline.side_effect = ["Generating message...\n", "Committing...\n", ""]
        process_mock.returncode = 0
        process_mock.wait.return_value = None
        mock_popen.return_value = process_mock
        
        # Setup Pass 2: Log Process
        mock_run.return_value.stdout = "commit 12345"
        mock_run.return_value.returncode = 0
        
        config = {"configurable": {"thread_id": "session-commit"}}
        
        # Run
        result = run_commit.func(config=config)
        
        # Verify Streaming
        assert mock_event_bus.publish.call_count == 2
        args1 = mock_event_bus.publish.call_args_list[0][0]
        assert args1[0] == "session-commit"
        assert "Generating message" in args1[2]
        
        assert "Commit successful" in result
