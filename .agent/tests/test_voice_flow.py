from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.speech.interfaces import STTProvider, TTSProvider

# Mock Providers
class MockSTT(STTProvider):
    async def listen(self, audio_data: bytes) -> str:
        return "mocked transcript"
    async def health_check(self) -> bool:
        return True

class MockTTS(TTSProvider):
    async def speak(self, text: str) -> bytes:
        return b"mocked audio"
    async def health_check(self) -> bool:
        return True

client = TestClient(app)

def test_websocket_connect():
    # Mock the factory to return our mock providers
    with patch("backend.voice.orchestrator.get_voice_providers", return_value=(MockSTT(), MockTTS())):
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_bytes(b"hello audio")
            
            # We expect the orchestrator to:
            # 1. Receive "mocked transcript" from MockSTT
            # 2. Agent (stubbed) responds
            # 3. TTS produces "mocked audio"
            # 4. WebSocket sends "mocked audio" back
            
            data = websocket.receive_bytes()
            assert data == b"mocked audio"
