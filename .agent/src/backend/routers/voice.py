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


import asyncio

@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for handling voice interactions with Barge-in support.
    
    Architecture:
    - Sender Task: consumes audio_queue -> sends to client
    - Receiver Loop: reads input -> VAD check -> offloads processing
    """
    await websocket.accept()
    session_id = str(uuid4())
    logger.info(f"Voice session started: {session_id}", extra={"correlation_id": session_id})
    
    orchestrator = VoiceOrchestrator(session_id)
    
    # Unified output queue for audio and JSON events
    output_queue = asyncio.Queue()

    # Callback to route Orchestrator events (tool calls, transcripts) to client
    def on_event_callback(event_type: str, payload: dict):
        # We use put_nowait because this is called synchronously from orchestrator
        output_queue.put_nowait(("json", {"type": event_type, **payload}))
    
    orchestrator.on_event = on_event_callback
    
    # 1. Start Orchestrator Background Worker
    orchestrator.run_background(output_queue)
    
    async def unified_sender_task():
        """Background task to stream audio and events to the client."""
        try:
            while True:
                item = await output_queue.get()
                if item is None:  # Sentinel
                    break
                
                msg_type, data = item
                if msg_type == "audio":
                    await websocket.send_bytes(data)
                elif msg_type == "json":
                    await websocket.send_json(data)

                output_queue.task_done()
        except Exception as e:
            logger.error(f"Sender task error: {e}")

    sender_future = asyncio.create_task(unified_sender_task())
    
    try:
        while True:
            # 1. Receive (Wait for input)
            data = await websocket.receive_bytes()
            
            # 2. Sequential Processing
            # We push every chunk to the orchestrator.
            # Its worker loop handles VAD, Endpointing, and Barge-in sequentially.
            orchestrator.push_audio(data)
            
    except WebSocketDisconnect:
        logger.info(f"Voice session ended: {session_id}", extra={"correlation_id": session_id})
    except Exception as e:
        logger.error(f"Voice session error: {e}", extra={"correlation_id": session_id})
        await websocket.close(code=1011)
    finally:
        # Cleanup
        orchestrator.stop()
        await output_queue.put(None) # Stop sender
        await sender_future


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get chat history for a session."""
    from backend.voice.orchestrator import get_chat_history
    history = await get_chat_history(session_id)
    return {"history": history}