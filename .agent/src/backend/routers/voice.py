from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import logging
from uuid import uuid4

from backend.voice.orchestrator import VoiceOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for handling voice interactions.
    """
    await websocket.accept()
    session_id = str(uuid4())
    logger.info(f"Voice session started: {session_id}", extra={"correlation_id": session_id})
    
    orchestrator = VoiceOrchestrator(session_id)
    
    try:
        while True:
            # Expecting raw audio bytes or JSON with base64? 
            # Supporting raw bytes for simplicity/speed
            data = await websocket.receive_bytes()
            
            # Application Logic
            response_audio = await orchestrator.process_audio(data)
            
            if response_audio:
                await websocket.send_bytes(response_audio)
                
    except WebSocketDisconnect:
        logger.info(f"Voice session ended: {session_id}", extra={"correlation_id": session_id})
    except Exception as e:
        logger.error(f"Voice session error: {e}", extra={"correlation_id": session_id})
        await websocket.close(code=1011) # Internal Error