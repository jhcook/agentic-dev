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

from typing import Callable, Dict, Any, List
import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

class EventBus:
    """
    Simple in-memory event bus to decouple Tools (subprocess execution)
    from the Orchestrator (WebSocket streaming).
    """
    _instance = None
    _subscribers: Dict[str, List[Callable[[str, Any], None]]] = defaultdict(list)
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
        return cls._instance


    @classmethod
    def subscribe(cls, session_id: str, callback: Callable[[str, Any], None]):
        """
        Subscribe a callback to events for a specific session.
        ENFORCES SINGLE SUBSCRIBER: Overwrites any existing subscriber for this session
        to prevent duplicate outputs in case of race conditions or zombie connections.
        Uses weak references to prevent memory leaks.
        """
        import weakref
        
        with cls._lock:
            # We need to wrap the callback method if it's a bound method
            # WeakMethod is robust for bound methods.
            if hasattr(callback, '__self__') and callback.__self__ is not None:
                ref = weakref.WeakMethod(callback)
            else:
                ref = weakref.ref(callback)
                
            cls._subscribers[session_id] = [ref]

    @classmethod
    def unsubscribe(cls, session_id: str, callback: Callable = None):
        """
        Remove subscriber.
        Args:
            session_id: Session to unsubscribe
            callback: Specific callback to remove. If None, removes all (legacy behavior).
        """
        with cls._lock:
            if session_id in cls._subscribers:
                if callback:
                    # Filter out the specific callback
                    # We have to dereference weakrefs to compare
                    new_list = []
                    for ref in cls._subscribers[session_id]:
                        obj = ref()
                        if obj is not None and obj != callback:
                            new_list.append(ref)
                    cls._subscribers[session_id] = new_list
                else:
                    # Force remove all
                    del cls._subscribers[session_id]
                
                # Cleanup if empty
                if session_id in cls._subscribers and not cls._subscribers[session_id]:
                    del cls._subscribers[session_id]

    @classmethod
    def publish(cls, session_id: str, event_type: str, data: Any):
        """Publish an event to the subscriber of a session."""
        with cls._lock:
            if session_id in cls._subscribers:
                # Iterate over copy
                # Dereference weakrefs
                active_refs = []
                for ref in list(cls._subscribers[session_id]):
                    callback = ref()
                    if callback is not None:
                        try:
                            callback(event_type, data)
                            active_refs.append(ref)
                        except Exception as e:
                            logger.error(f"EventBus callback failed: {e}")
                    # If callback is None, it's dead, don't keep it
                
                # Update list with only active refs
                if active_refs:
                    cls._subscribers[session_id] = active_refs
                else:
                    del cls._subscribers[session_id]
