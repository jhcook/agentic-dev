import pytest
from unittest.mock import MagicMock, patch
from backend.voice.tools.git import get_git_status, get_git_diff
from backend.voice.events import EventBus

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
    
    # Check streaming (streams full content though? code says: EventBus.publish(..., result.stdout))
    # Wait, code says:
    # EventBus.publish(session_id, "console", "\n=== Git Diff (Staged) ===\n" + result.stdout)
    # The return value is truncated, but the stream might not be in the current impl. 
    # Let's check the implementation logic we saw earlier.
    # Step 149: 
    # if len(result.stdout) > 5000: return result.stdout[:5000] + ...
    # EventBus.publish(..., result.stdout) <-- It publishes the FULL stdout before truncation return?
    # Actually checking the code:
    # 113: if len > 5000: return ...
    # 116: if config: EventBus.publish(..., result.stdout)
    # The publish uses the full result.stdout.
    
    mock_event_bus.publish.assert_called_once()
    args = mock_event_bus.publish.call_args[0]
    assert len(args[2]) >= 6000 # Should stream full content
