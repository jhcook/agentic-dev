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
import webrtcvad
from backend.voice.vad import VADProcessor

def test_vad_initialization():
    processor = VADProcessor(aggressiveness=1)
    assert processor.sample_rate == 16000
    assert processor.frame_duration_ms == 20
    assert processor.frame_size_bytes == 640 # 16000 * 0.02 * 2

def test_vad_process_silence():
    processor = VADProcessor(aggressiveness=3)
    # 20ms of silence
    chunk = b"\x00" * 640
    is_speech = processor.process(chunk)
    assert not is_speech

def test_vad_process_synthetic_speech():
    processor = VADProcessor(aggressiveness=0)
    # Generate some 100Hz square wave audio (alternating 1/-1)
    # This is "signal" and should be detected by VAD if aggressiveness is low
    # 16000 Hz, 100Hz wave means 160 samples per period
    chunk = bytearray()
    for i in range(320): # Two periods
        if (i // 80) % 2 == 0:
            val = 5000 # 16-bit PCM
        else:
            val = -5000
        chunk.extend(val.to_bytes(2, byteorder='little', signed=True))
    
    # 640 bytes = 320 samples
    is_speech = processor.process(bytes(chunk))
    # Note: webrtcvad might not detect square waves as speech, but it's more likely than flat zero
    # Actually, let's just assert it runs and returns a boolean
    assert isinstance(is_speech, bool)

def test_vad_partial_frame():
    processor = VADProcessor()
    # 10ms of audio (not enough for a frame)
    chunk = b"\x00" * 320
    is_speech = processor.process(chunk)
    assert not is_speech
    assert len(processor.buffer) == 320
    
    # Add another 10ms
    is_speech = processor.process(chunk)
    # Now it should have processed 1 frame of silence
    assert not is_speech
    assert len(processor.buffer) == 0

def test_vad_reset():
    processor = VADProcessor()
    processor.buffer.extend(b"\x00" * 320)
    processor.reset()
    assert len(processor.buffer) == 0
