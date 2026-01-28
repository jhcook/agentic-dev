
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
from backend.voice.events import EventBus

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
    assert "UNTRACKED Files" in result
    
    # Check streaming
    mock_event_bus.publish.assert_called_once()
    args = mock_event_bus.publish.call_args[0]
    assert args[0] == "session-1" # Session ID
    assert args[1] == "console"
    assert "=== Git Status ===" in args[2]

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
