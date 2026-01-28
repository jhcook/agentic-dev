import pytest
import subprocess
from unittest.mock import MagicMock, patch
from backend.voice.process_manager import ProcessLifecycleManager
import threading

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

@pytest.fixture(autouse=True)
def cleanup_manager():
    """Reset singleton and processes before/after each test"""
    # Reset singleton
    ProcessLifecycleManager._instance = None
    manager = ProcessLifecycleManager.instance()
    yield manager
    # Cleanup
    manager.kill_all()
    ProcessLifecycleManager._instance = None

def test_singleton_pattern():
    """Verify that only one instance of the manager is created."""
    m1 = ProcessLifecycleManager.instance()
    m2 = ProcessLifecycleManager.instance()
    assert m1 is m2

def test_register_and_retrieve():
    """Verify that we can register a process and get it back by ID."""
    manager = ProcessLifecycleManager.instance()
    mock_process = MagicMock(spec=subprocess.Popen)
    mock_process.pid = 12345
    
    # Register with explicit ID
    pid = manager.register(mock_process, "test-proc-1")
    assert pid == "test-proc-1"
    
    # Retrieve
    retrieved = manager.get("test-proc-1")
    assert retrieved is mock_process
    
    # Unregister
    manager.unregister("test-proc-1")
    assert manager.get("test-proc-1") is None

def test_register_auto_id():
    """Verify registration uses PID if no ID provided."""
    manager = ProcessLifecycleManager.instance()
    mock_process = MagicMock(spec=subprocess.Popen)
    mock_process.pid = 67890
    
    pid = manager.register(mock_process)
    assert pid == "67890"
    assert manager.get("67890") is mock_process

def test_kill_all():
    """Verify kill_all terminates all registered processes."""
    manager = ProcessLifecycleManager.instance()
    
    p1 = MagicMock(spec=subprocess.Popen)
    p1.pid = 1001
    p1.poll.return_value = None # Running
    
    p2 = MagicMock(spec=subprocess.Popen)
    p2.pid = 1002
    p2.poll.return_value = 0 # Already exited
    
    manager.register(p1, "p1")
    manager.register(p2, "p2")
    
    manager.kill_all()
    
    # p1 should be terminated
    p1.terminate.assert_called_once()
    # p2 should NOT be terminated (already dead)
    p2.terminate.assert_not_called()
    
    # List should be empty
    assert manager.get("p1") is None
    assert manager.get("p2") is None
