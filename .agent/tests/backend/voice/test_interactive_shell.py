import pytest
from unittest.mock import MagicMock, patch
from backend.voice.tools.interactive_shell import start_interactive_shell, send_shell_input
from backend.voice.process_manager import ProcessLifecycleManager

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
def mock_lifecycle():
    with patch('backend.voice.tools.interactive_shell.ProcessLifecycleManager') as mock:
        instance = mock.instance.return_value
        yield instance

@pytest.fixture
def mock_subprocess():
    with patch('subprocess.Popen') as mock_popen:
        process = MagicMock()
        process.stdout.readline.side_effect = ['line1\n', 'line2\n', '']
        process.wait.return_value = 0
        process.stdin = MagicMock()
        mock_popen.return_value = process
        yield mock_popen

def test_start_interactive_shell(mock_lifecycle, mock_subprocess):
    """Test starting a shell registers the process and returns an ID."""
    
    config = {"configurable": {"thread_id": "test-session"}}
    
    with patch('backend.voice.tools.interactive_shell.threading.Thread'):
        # Use .func to bypass StructuredTool wrapper
        result = start_interactive_shell.func("ls -la", config=config)
    
    # Verify subprocess called
    mock_subprocess.assert_called_once()
    
    # Verify registered
    mock_lifecycle.register.assert_called_once()
    
    assert "Started interactive process" in result
    assert "ID: shell-" in result

def test_send_shell_input(mock_lifecycle):
    """Test sending input writes to stdin."""
    
    # Setup mock process
    mock_process = MagicMock()
    mock_process.poll.return_value = None # Running
    mock_lifecycle.get.return_value = mock_process
    
    # Use .func
    result = send_shell_input.func("proc-123", "yes")
    
    mock_lifecycle.get.assert_called_with("proc-123")
    mock_process.stdin.write.assert_called_with("yes\n")
    mock_process.stdin.flush.assert_called_once()
    assert "Sent input" in result

def test_send_shell_input_not_found(mock_lifecycle):
    """Test error when process not found."""
    mock_lifecycle.get.return_value = None
    result = send_shell_input.func("proc-missing", "foo")
    assert "Error: Process proc-missing not found" in result

def test_send_shell_input_exited(mock_lifecycle):
    """Test error when process already exited."""
    mock_process = MagicMock()
    mock_process.poll.return_value = 0 # Exited
    mock_lifecycle.get.return_value = mock_process
    
    result = send_shell_input.func("proc-dead", "foo")
    assert "has already exited" in result
