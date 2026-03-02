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
from unittest.mock import MagicMock, AsyncMock, patch
from backend.voice.orchestrator import VoiceOrchestrator
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

@pytest.mark.asyncio
async def test_mute_force_flush_logic():
    """Test that Mute Sentinel forces processing even if VAD didn't trigger fully."""
    
    # Mock VAD to simulate "No Speech" (e.g. too short or quiet)
    with patch('backend.voice.vad.VADProcessor') as MockVAD:
        orchestrator = VoiceOrchestrator("test-session")
        orchestrator.vad.process.return_value = False # Never detects speech
        orchestrator._run_pipeline = AsyncMock() # Spy on pipeline
        orchestrator.logger = MagicMock()
        
        # 1. Start the loop
        queue = asyncio.Queue()
        orchestrator.run_background(queue)
        
        try:
            # 2. Push some "Quiet" audio (below threshold but non-zero)
            # 0.5 seconds of audio
            audio_chunk = b'\x00' * 3200 # 3200 bytes = 0.1s at 16k 16bit? 16000 * 2 = 32000 bytes/s. 3200 is 0.1s.
            for _ in range(5):
                orchestrator.push_audio(audio_chunk)
                
            # 3. Send Mute Sentinel (User clicked Mute)
            # Simulate router handling mute_changed
            orchestrator.handle_client_event("mute_changed", {"muted": True})
            
            # Allow loop to process
            await asyncio.sleep(0.1)
            
            # 4. Verify Pipeline was called?
            # CURRENTLY: This should FAIL because speech_active is False.
            # We WANT it to Pass (Push-to-Talk behavior).
            
            # Check if pipeline was called
            # orchestrator._run_pipeline.assert_called() 
            
            print(f"Pipeline called: {orchestrator._run_pipeline.called}")
            
            # We assert what we EXPECT the current behavior to be (reproduction)
            # If this fails assertion, then my understanding is wrong.
            # Expectation: called=True (Push-to-Talk works)
            assert orchestrator._run_pipeline.called, "Pipeline WAS NOT called, Push-to-Talk failed."
        finally:
            orchestrator.stop()

