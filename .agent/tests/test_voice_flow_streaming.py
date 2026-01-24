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


import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.voice.orchestrator import VoiceOrchestrator

# Mock providers
class MockSTT:
    async def listen(self, audio): return "user input"

class MockTTS:
    async def speak(self, text): 
        # Return the text itself as bytes so we can verify what was sent to TTS
        return text.encode('utf-8')

@pytest.fixture
def mock_providers():
    with patch("backend.voice.orchestrator.get_voice_providers") as mock:
        mock.return_value = (MockSTT(), MockTTS())
        yield mock

@pytest.mark.asyncio
async def test_process_audio_streaming(mock_providers):
    orchestrator = VoiceOrchestrator("test-session")
    
    # Mock _invoke_agent to yield tokens slowly
    # Simulating: "One. Two. Three."
    async def mock_agent_stream(text):
        tokens = ["One", ".", " ", "Two", ".", " ", "Three", "."]
        for t in tokens:
            yield t
            
    orchestrator._invoke_agent = mock_agent_stream
    
    # Run pipeline
    audio_chunks = []
    # Send enough audio to trigger the accumulation buffer (1.5s = 48000 bytes)
    async for chunk in orchestrator.process_audio(b"\x00" * 48000):
        audio_chunks.append(chunk)
        
    # Verification
    # Expected chunks based on SentenceBuffer logic:
    # 1. "One."
    # 2. "Two."
    # 3. "Three."
    
    assert len(audio_chunks) == 3
    assert audio_chunks[0] == b"One."
    assert audio_chunks[1] == b"Two."
    assert audio_chunks[2] == b"Three."

@pytest.mark.asyncio
async def test_process_audio_no_input(mock_providers):
    orchestrator = VoiceOrchestrator("test-session")
    orchestrator.stt.listen = AsyncMock(return_value="")
    
    chunks = [c async for c in orchestrator.process_audio(b"")]
    assert len(chunks) == 0
