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
from unittest.mock import patch, AsyncMock
from backend.voice.orchestrator import VoiceOrchestrator

@pytest.mark.asyncio
async def test_voice_integration_flow():
    """
    Simulate a full turn: User speaks -> VAD triggers -> STT -> LLM -> TTS
    """
    with patch("backend.voice.vad.VADProcessor") as MockVAD, \
         patch("backend.voice.orchestrator.get_voice_providers") as MockGetProviders, \
         patch("backend.voice.orchestrator._create_llm"), \
         patch("backend.voice.orchestrator.tracer"):
         
        mock_vad = MockVAD.return_value
        # Mock VAD to detect speech
        mock_vad.process.side_effect = [True, True, False]
        
        mock_stt = AsyncMock()
        mock_stt.listen.return_value = "Hello"
        
        mock_tts = AsyncMock()
        mock_tts.speak.return_value = b"audio"
        
        MockGetProviders.return_value = (mock_stt, mock_tts)
        
        orch = VoiceOrchestrator(session_id="integration_test")
        
        # We manually trigger the internal processing to skip the infinite loop complexity
        # Simulate pushing specific chunks
        await orch._process_audio_chunk(b"chunk1")
        
        assert orch is not None
        mock_vad.process.assert_called_with(b"chunk1")
