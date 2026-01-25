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
    audio_queue = asyncio.Queue()
    
    async def sender_task():
        """Background task to stream audio and events to the client."""
        try:
            while True:
                # Merge queues or use a priority selector?
                # Simple round-robin for now
                
                # 1. Check Audio
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.01)
                    if chunk is None: break
                    await websocket.send_bytes(chunk)
                    audio_queue.task_done()
                except asyncio.TimeoutError:
                    pass
                
                # 2. Check Events (Transcript Sync)
                # We need a way to get events from orchestrator.
                # For MVP, we'll let orchestrator emit to log_bus and we intercept?
                # Or better, we pass a callback to orchestrator.
                pass
                
        except Exception as e:
            logger.error(f"Sender task error: {e}")

    # Better approach: Shared Queue for everything
    # (type, data) tuple
    output_queue = asyncio.Queue()
    
    async def unified_sender():
        try:
            while True:
                item = await output_queue.get()
                if item is None: break
                
                msg_type, data = item
                
                if msg_type == "audio":
                    await websocket.send_bytes(data)
                elif msg_type == "json":
                    await websocket.send_json(data)
                    
                output_queue.task_done()
        except Exception as e:
            logger.error(f"Unified sender error: {e}")

    # Pass a callback to orchestrator to emit events
    def on_event(event_type: str, payload: dict):
        # "transcript.user", "transcript.agent", "tool.start", "tool.end"
        asyncio.create_task(output_queue.put(("json", {"type": event_type, "payload": payload})))
        
    # We need to monkeypatch or inject this into orchestrator instance
    orchestrator.on_event = on_event 

    async def process_input_background(data: bytes):
        """Worker to process audio and push response to queue."""
        try:
            async for audio_chunk in orchestrator.process_audio(data):
                await output_queue.put(("audio", audio_chunk))
        except Exception as e:
            logger.error(f"Processing error: {e}")

    sender_future = asyncio.create_task(unified_sender())
    
    try:
        while True:
            # 1. Receive (Wait for input)
            data = await websocket.receive_bytes()
            
            # 2. Interrupt Check
            if orchestrator.process_vad(data):
                if orchestrator.is_speaking.is_set():
                    logger.info(f"Interrupt detected in session {session_id}")
                    orchestrator.interrupt()
                    
                    # Clear Queue
                    while not output_queue.empty():
                        try:
                            output_queue.get_nowait()
                            output_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                    
                    await websocket.send_json({"type": "clear_buffer"})
            
            # 3. Offload
            asyncio.create_task(process_input_background(data))
            
    except WebSocketDisconnect:
        logger.info(f"Voice session ended: {session_id}", extra={"correlation_id": session_id})
    except Exception as e:
        logger.error(f"Voice session error: {e}", extra={"correlation_id": session_id})
        await websocket.close(code=1011)
    finally:
        await output_queue.put(None)
        await sender_future