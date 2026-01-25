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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.routers import voice, admin, governance
from backend.admin.logger import log_bus
import json
import time

app = FastAPI(title="Agentic Voice Backend")

app.include_router(voice.router)
app.include_router(admin.router)
app.include_router(governance.router)

@app.websocket("/ws/admin/logs")
async def admin_logs_websocket(websocket: WebSocket):
    """Streams activity logs from the internal log_bus to the frontend."""
    await websocket.accept()
    queue = await log_bus.subscribe()
    try:
        # Send a connection confirmation
        await websocket.send_text(json.dumps({
            "timestamp": time.time(),
            "type": "info",
            "content": "Connected to Activity Stream",
            "level": "info"
        }))
        
        while True:
            # Wait for a log message from the bus
            message = await queue.get()
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        log_bus.unsubscribe(queue)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
