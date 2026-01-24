
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from backend.main import app
import asyncio

@pytest.fixture
def client():
    return TestClient(app)

def test_interrupt_flow(client):
    # Mock Orchestrator
    with patch("backend.routers.voice.VoiceOrchestrator") as check_mock:
        mock_orch = MagicMock()
        check_mock.return_value = mock_orch
        
        # Setup: VAD returns True => Speech detected
        mock_orch.process_vad.return_value = True
        
        # Setup: is_speaking event is set => Agent IS speaking
        # We need a real threading/asyncio Event or a mock that behaves like one
        # `is_set()` must return True
        mock_event = MagicMock()
        mock_event.is_set.return_value = True
        mock_orch.is_speaking = mock_event
        
        # process_audio mock (async generator)
        async def mock_gen(data):
            yield b"audio_chunk"
        mock_orch.process_audio.side_effect = mock_gen
        
        # Test Websocket
        with client.websocket_connect("/ws/voice") as websocket:
            # Send audio (bytes)
            websocket.send_bytes(b"dummy audio")
            
            # Expect "clear_buffer" JSON message due to VAD interrupt
            # The router should prioritize the interrupt check
            data = websocket.receive_json()
            assert data == {"type": "clear_buffer"}
            
            # Verify interrupt was called
            mock_orch.interrupt.assert_called()

def test_no_interrupt_when_silent(client):
    with patch("backend.routers.voice.VoiceOrchestrator") as check_mock:
        mock_orch = MagicMock()
        check_mock.return_value = mock_orch
        
        # Setup: VAD returns False => Silence
        mock_orch.process_vad.return_value = False
        
        mock_event = MagicMock()
        mock_event.is_set.return_value = True
        mock_orch.is_speaking = mock_event
        
        async def mock_gen(data):
            yield b"response_audio"
        mock_orch.process_audio.side_effect = mock_gen
        
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_bytes(b"silence")
            
            # Should receive audio bytes response (from mock_gen), NOT clear_buffer
            # Note: TestClient WebSocket API might vary on receive type handling
            # receive_bytes()
            data = websocket.receive_bytes()
            assert data == b"response_audio"
            
            # interrupt should NOT have been called
            mock_orch.interrupt.assert_not_called()
