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
        """Subscribe a callback to events for a specific session."""
        with cls._lock:
            cls._subscribers[session_id].append(callback)

    @classmethod
    def unsubscribe(cls, session_id: str):
        """Remove all subscribers for a session."""
        with cls._lock:
            if session_id in cls._subscribers:
                del cls._subscribers[session_id]

    @classmethod
    def publish(cls, session_id: str, event_type: str, data: Any):
        """Publish an event to all subscribers of a session."""
        with cls._lock:
            if session_id in cls._subscribers:
                for callback in cls._subscribers[session_id]:
                    try:
                        callback(event_type, data)
                    except Exception as e:
                        logger.error(f"EventBus callback failed: {e}")
