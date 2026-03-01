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
from backend.routers import governance
from backend.admin.logger import log_bus
import logging
import json
import time

logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic Voice Backend")

from starlette.types import ASGIApp, Receive, Scope, Send

class PermissiveASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            # 1. Log Origin
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode("utf-8")
            logger.info(f"HTTP Request: {scope.get('path')} | Origin: {origin}")
            
            # 2. Add CORS headers to response
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    if origin:
                        headers[b"access-control-allow-origin"] = origin.encode("utf-8")
                        headers[b"access-control-allow-credentials"] = b"true"
                        headers[b"access-control-allow-methods"] = b"*"
                        headers[b"access-control-allow-headers"] = b"*"
                    message["headers"] = [[k, v] for k, v in headers.items()]
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
            
        elif scope["type"] == "websocket":
            # 1. Log Origin (Handshake)
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode("utf-8")
            logger.info(f"WebSocket Handshake: {scope.get('path')} | Origin: {origin}")
            
            # 2. Allow everything (No-op, just pass through)
            # If something else was blocking it, this wrapper helps us see it.
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)

app.add_middleware(PermissiveASGIMiddleware)

# Optional: Voice Capabilities
try:
    from backend.routers import voice
    app.include_router(voice.router)
    logger.info("Voice module loaded")
except ImportError:
    logger.warning("Voice dependencies missing. Voice capabilities disabled.")

# Optional: Admin Capabilities
try:
    from backend.routers import admin
    app.include_router(admin.router)
    logger.info("Admin module loaded")
except ImportError:
    logger.warning("Admin dependencies missing. Admin capabilities disabled.")

try:
    from backend.routers import dashboard
    app.include_router(dashboard.router)
    logger.info("Dashboard module loaded")
except ImportError:
    logger.warning("Dashboard module failed to load.")

app.include_router(governance.router)

# Optional: Premium Voice Capabilities (Agentic Executive)
try:
    from agentic_executive import voice_router
    app.include_router(voice_router, prefix="/voice", tags=["premium-voice"])
    logger.info("Agentic Executive (Premium) Voice module loaded")
except ImportError:
    pass
except Exception as e:
    logger.warning(f"Failed to load Agentic Executive: {e}")

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
