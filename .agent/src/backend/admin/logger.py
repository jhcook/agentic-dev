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

import asyncio
import json
import time
from typing import Set

class ActivityLogBus:
    """A simple event bus to broadcast agent activity to WebSocket clients."""
    
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._clients.discard(queue)

    def broadcast(self, type: str, content: str, level: str = "info"):
        message = {
            "timestamp": time.time(),
            "type": type,    # 'thought', 'tool', 'error', 'info'
            "content": content,
            "level": level
        }
        raw = json.dumps(message)
        for queue in self._clients:
            queue.put_nowait(raw)

# Singleton
log_bus = ActivityLogBus()
