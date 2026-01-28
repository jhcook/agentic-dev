import pytest
import threading
import time
from backend.voice.events import EventBus
from collections import defaultdict

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
def reset_event_bus():
    """Reset subscribers between tests"""
    EventBus._subscribers = defaultdict(list)
    yield
    EventBus._subscribers = defaultdict(list)

def test_subscribe_publish():
    """Verify basic pub/sub functionality."""
    received = []
    def callback(event_type, data):
        received.append((event_type, data))
        
    EventBus.subscribe("session-1", callback)
    EventBus.publish("session-1", "test_event", "hello")
    
    assert len(received) == 1
    assert received[0] == ("test_event", "hello")

def test_unsubscribe():
    """Verify unsubscribe removes callbacks."""
    received = []
    def callback(event_type, data):
        received.append((event_type, data))
        
    EventBus.subscribe("session-1", callback)
    EventBus.unsubscribe("session-1")
    EventBus.publish("session-1", "test_event", "hello")
    
    assert len(received) == 0

def test_wrong_session():
    """Verify events are isolated by session ID."""
    received = []
    def callback(event_type, data):
        received.append((event_type, data))
        
    EventBus.subscribe("session-A", callback)
    EventBus.publish("session-B", "test_event", "hello")
    
    assert len(received) == 0

def test_thread_safety_concurrency():
    """Verify that publishing from multiple threads is safe."""
    
    # Setup: 100 threads publishing 100 events each to the same session
    session_id = "concurrent-session"
    events_received = []
    
    def callback(event_type, data):
        # Even the callback append needs to be somewhat safe if called concurrently, 
        # but in CPython list append is atomic.
        events_received.append(data)
        
    EventBus.subscribe(session_id, callback)
    
    def worker(worker_id):
        for i in range(100):
            EventBus.publish(session_id, "ping", f"{worker_id}-{i}")
            
    threads = []
    for i in range(50):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Validation
    assert len(events_received) == 50 * 100
    
    # Also verify structural integrity (no exceptions were raised during publish)
    # The 'subscribers' dict should still be valid
    assert len(EventBus._subscribers[session_id]) == 1
