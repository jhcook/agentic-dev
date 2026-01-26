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

import logging
import webrtcvad

logger = logging.getLogger(__name__)

class VADProcessor:
    """
    Voice Activity Detection using Google WebRTC VAD.
    Standard, lightweight, and low-latency.
    """
    def __init__(self, aggressiveness: int = 1, sample_rate: int = 16000):
        """
        Args:
            aggressiveness: 0 (Least aggressive about filtering non-speech) to 3 (Most aggressive).
            sample_rate: 8000, 16000, 32000, or 48000 Hz.
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = 20
        self.frame_size_bytes = int(sample_rate * (self.frame_duration_ms / 1000.0) * 2) # 16-bit
        self.buffer = bytearray()
        
    def process(self, audio_chunk: bytes) -> bool:
        """
        Process incoming audio chunk. 
        Returns True if ANY speech is detected in the processed frames.
        """
        self.buffer.extend(audio_chunk)
        
        speech_found = False
        
        # Process all complete frames in buffer
        while len(self.buffer) >= self.frame_size_bytes:
            frame = bytes(self.buffer[:self.frame_size_bytes])
            del self.buffer[:self.frame_size_bytes]
            
            try:
                is_speech = self.vad.is_speech(frame, self.sample_rate)
                if is_speech:
                    speech_found = True
            except Exception as e:
                logger.error(f"WebRTC VAD Error: {e}")
                
        return speech_found

    def reset(self):
        """Reset buffer."""
        self.buffer.clear()
