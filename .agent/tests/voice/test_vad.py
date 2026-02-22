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
from unittest.mock import MagicMock, patch
np = pytest.importorskip("numpy", reason="requires voice extras (numpy)")
from backend.voice.vad import VADProcessor

# Mock OpenTelemetry
@pytest.fixture(autouse=True)
def mock_otel():
    with patch('backend.voice.vad.tracer') as mock_tracer:
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        yield mock_tracer

def test_vad_initialization_defaults():
    vad = VADProcessor()
    assert vad.aggressiveness == 3
    assert vad.threshold == 0.5
    assert vad.autotune is False

def test_vad_autotune_logic():
    vad = VADProcessor(autotune=True)
    # Mock audio chunk (silence)
    chunk = np.zeros(16000, dtype=np.int16).tobytes()
    
    # Run calibration
    for _ in range(30):
        vad.process(chunk)
        
    assert vad.calibrated is True
    assert vad.ambient_noise_level == 0.0

def test_energy_fallback():
    vad = VADProcessor()
    # Force energy mode
    vad.use_energy = True
    vad.silero_session = None
    vad.webrtc_vad = None
    
    # Force calibrated state to avoid warmup period
    vad.calibrated = True

    # Silence
    chunk_silence = np.zeros(1000, dtype=np.int16).tobytes()
    
    # We need to simulate taking it out of calibration mode first so it processes
    vad.calibration_frames = 25
    vad.calibrated = True
    
    assert vad.process(chunk_silence) is False
    
    # Loud noise (simulate speech)
    # Max amplitude is 32767
    chunk_loud = (np.ones(1000, dtype=np.int16) * 10000).tobytes()
    assert vad.process(chunk_loud) is True

def test_otel_tracing_on_process(mock_otel):
    vad = VADProcessor()
    vad.use_energy = True # Simplest path
    vad.silero_session = None
    vad.webrtc_vad = None
    vad.calibration_frames = 25
    vad.calibrated = True
    
    chunk_loud = (np.ones(1000, dtype=np.int16) * 10000).tobytes()
    
    # Ensure it returns True so tracing fires
    result = vad.process(chunk_loud)
    assert result is True
    
    # Verify tracer was called (use the mock from the autouse fixture)
    mock_otel.start_as_current_span.assert_called()
