import pytest
import time
import threading
from backend.voice.tools.interactive_shell import start_interactive_shell
from backend.voice.events import EventBus
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

@pytest.fixture(autouse=True)
def cleanup():
    """Ensure cleanup of processes."""
    yield
    ProcessLifecycleManager.instance().kill_all()
    # clean event listeners
    # Access private dict to clean (for tests only)
    EventBus._subscribers.clear()

def test_e2e_console_streaming():
    """
    E2E Test: Start a real subprocess, verify output streams to EventBus.
    No mocks used for ProcessManager, EventBus, or Subprocess.
    """
    session_id = "test-session-e2e"
    received_lines = []
    
    # Synchronization
    done_event = threading.Event()
    
    def callback(event_type, data):
        if event_type == "console":
            received_lines.append(data)
            if "hello world" in data:
                done_event.set()
                
    EventBus.subscribe(session_id, callback)
    
    config = {"configurable": {"thread_id": session_id}}
    
    # Execute REAL command
    # Use 'sh -c' to ensure it runs similarly to shell=True
    # We use the tool's logic which does shell=True
    result = start_interactive_shell.func("echo 'hello world'", config=config)
    
    # Verify tool return
    assert "Started interactive process" in result
    
    # Wait for async streaming (max 2 seconds)
    is_set = done_event.wait(timeout=2.0)
    
    # Assertions
    if not is_set:
        print(f"Captured lines ({len(received_lines)}): {received_lines}")
        
    assert is_set, "Did not receive 'hello world' via EventBus within timeout"
    
    # Verify process cleanup happens eventually
    # Give it a moment to exit
    time.sleep(0.1)
    # Manager should be empty (unregister calls unregister)
    # Note: ProcessLifecycleManager.unregister is called when thread finishes
    
    # We can check explicitly
    # But for now, main goal is streaming verification.
