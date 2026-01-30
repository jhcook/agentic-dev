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
import asyncio
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
    with patch("backend.voice.orchestrator.get_voice_providers") as mock_providers, \
         patch("backend.voice.orchestrator._create_llm") as mock_llm_factory:
        mock_providers.return_value = (MockSTT(), MockTTS())
        mock_llm_factory.return_value = MagicMock() # Mock LLM
        yield mock_providers

@pytest.mark.asyncio
async def test_process_audio_streaming(mock_providers):
    orchestrator = VoiceOrchestrator("test-session")
    orchestrator.output_queue = asyncio.Queue()
    async def mock_run_pipeline(audio_data, gen_id):
        tokens = ["One.", "Two.", "Three."]
        for t in tokens:
            await orchestrator.output_queue.put({"type": "audio", "data": t.encode('utf-8')})
            
    orchestrator._run_pipeline = mock_run_pipeline
    
    # Mock Tuning
    orchestrator.SILENCE_THRESHOLD = 0.1
    orchestrator.process_vad = MagicMock(side_effect=[True, False, False])
    orchestrator.RMS_THRESHOLD = 0
    
    # Push audio to worker: Speech then silence
    orchestrator.push_audio(b"\x01\x00" * 1600) # Speech
    orchestrator.push_audio(b"\x01\x00" * 1600) # Silence start
    
    # Run the worker loop for a bit in a task
    orchestrator.is_running = True
    loop_task = asyncio.create_task(orchestrator._process_loop())
    
    # Wait for silence to trigger (SILENCE_THRESHOLD=0.1)
    await asyncio.sleep(0.3)
    orchestrator.push_audio(b"\x01\x00" * 1600) # Trigger valve
    
    # Collect results from output_queue
    results = []
    try:
        # Wait for 3 sentences
        for i in range(3):
            print(f"Waiting for sentence {i}...")
            item = await asyncio.wait_for(orchestrator.output_queue.get(), timeout=5.0)
            print(f"Received item: {item.get('type')}")
            if item["type"] == "audio":
                results.append(item["data"])
    except asyncio.TimeoutError:
        print("Timed out waiting for output_queue")
        raise
    finally:
        loop_task.cancel()
        orchestrator.stop()

    # Verification
    # Expected chunks based on SentenceBuffer logic:
    # 1. "One."
    # 2. "Two."
    # 3. "Three."
    assert len(results) == 3
    assert results[0] == b"One."
    assert results[1] == b"Two."
    assert results[2] == b"Three."

@pytest.mark.asyncio
async def test_process_audio_no_input(mock_providers):
    orchestrator = VoiceOrchestrator("test-session")
    orchestrator.output_queue = asyncio.Queue()
    orchestrator.stt.listen = AsyncMock(return_value="")
    
    # Mock VAD to trigger
    orchestrator.process_vad = MagicMock(return_value=True)
    orchestrator.RMS_THRESHOLD = 0
    
    orchestrator.push_audio(b"\x00" * 3200)
    
    loop_task = asyncio.create_task(orchestrator._process_loop())
    
    try:
        # Should NOT get anything in output_queue except status updates maybe
        # but certainly no audio
        with pytest.raises(asyncio.TimeoutError):
            item = await asyncio.wait_for(orchestrator.output_queue.get(), timeout=0.5)
            # Filter status thinking/listening if they happen
            count = 0
            while item["type"] == "status":
                 item = await asyncio.wait_for(orchestrator.output_queue.get(), timeout=0.5)
                 count += 1
                 if count > 100:
                     raise RuntimeError("Infinite status loop detected in test")
            assert item is None # Should not happen
    finally:
        loop_task.cancel()
        orchestrator.stop()
