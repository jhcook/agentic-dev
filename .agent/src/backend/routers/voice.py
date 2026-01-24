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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
from uuid import uuid4
from collections import defaultdict
from datetime import datetime, timedelta

from backend.voice.orchestrator import VoiceOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiter (use Redis in production)
session_requests = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 20


def check_rate_limit(session_id: str) -> bool:
    """Check if session has exceeded rate limit."""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=1)
    
    # Remove old requests
    session_requests[session_id] = [
        req_time for req_time in session_requests[session_id]
        if req_time > cutoff
    ]
    
    # Check limit
    if len(session_requests[session_id]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    # Record this request
    session_requests[session_id].append(now)
    return True


@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for handling voice interactions.
    Includes rate limiting to prevent abuse.
    """
    await websocket.accept()
    session_id = str(uuid4())
    logger.info(f"Voice session started: {session_id}", extra={"correlation_id": session_id})
    
    orchestrator = VoiceOrchestrator(session_id)
    
    try:
        while True:
            # Expecting raw audio bytes
            data = await websocket.receive_bytes()
            
            # Rate limit check
            if not check_rate_limit(session_id):
                logger.warning(
                    f"Rate limit exceeded for session {session_id}",
                    extra={"correlation_id": session_id}
                )
                # Send error message as JSON
                await websocket.send_json({
                    "error": "Rate limit exceeded. Please wait a moment."
                })
                continue
            
            # Application Logic (Streaming)
            async for audio_chunk in orchestrator.process_audio(data):
                await websocket.send_bytes(audio_chunk)
                
    except WebSocketDisconnect:
        logger.info(f"Voice session ended: {session_id}", extra={"correlation_id": session_id})
    except Exception as e:
        logger.error(f"Voice session error: {e}", extra={"correlation_id": session_id})
        await websocket.close(code=1011)  # Internal Error