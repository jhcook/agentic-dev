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


import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Mock kokoro_onnx module BEFORE importing LocalTTS
mock_kokoro_module = MagicMock()
sys.modules["kokoro_onnx"] = mock_kokoro_module

import pytest
np = pytest.importorskip("numpy", reason="requires voice extras (numpy)")
from backend.speech.providers.local import LocalTTS, TARGET_SAMPLE_RATE

@pytest.fixture
def mock_kokoro():
    # Setup the mock class inside the module
    mock_instance = MagicMock()
    mock_kokoro_module.Kokoro.return_value = mock_instance
    
    # Mock create return value
    # (samples, sample_rate)
    mock_instance.create.return_value = (np.zeros(24000, dtype=np.float32), 24000)
    
    yield mock_kokoro_module.Kokoro

@pytest.fixture
def mock_scipy(monkeypatch):
    mock_resample = MagicMock()
    # Return resized array
    def side_effect(x, num):
        return np.zeros(num, dtype=np.float32)
    mock_resample.side_effect = side_effect
    
    # Patch scipy.signal in the target module
    with patch("backend.speech.providers.local.scipy.signal.resample", mock_resample):
        yield mock_resample

@pytest.fixture
def mock_path():
    with patch("backend.speech.providers.local.Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        MockPath.return_value.__truediv__.return_value.exists.return_value = True
        yield MockPath

@pytest.fixture
def local_tts(mock_path, mock_kokoro):
    return LocalTTS(model_dir="/tmp/mock/models")

@pytest.mark.asyncio
async def test_speak_resampling(local_tts, mock_scipy):
    """Test that audio is generated and resampled correctly."""
    text = "Hello world"
    await local_tts.speak(text)
    
    # Verify Kokoro called
    local_tts.kokoro.create.assert_called_once()
    
    # Verify resampling (24k -> 16k)
    mock_scipy.assert_called_once()
    args, _ = mock_scipy.call_args
    assert args[1] == 16000

@pytest.mark.asyncio
async def test_speak_no_resampling_needed(local_tts, mock_scipy):
    """Test optimized path."""
    local_tts.kokoro.create.return_value = (np.zeros(16000, dtype=np.float32), 16000)
    await local_tts.speak("Hello")
    mock_scipy.assert_not_called()

@pytest.mark.asyncio
async def test_initialization_failure():
    """Test failure if models missing."""
    with patch("backend.speech.providers.local.Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        MockPath.return_value.__truediv__.return_value.exists.return_value = False
        
        # Reload module to ensure fresh import logic if needed, 
        # but here we just instantiate class
        tts = LocalTTS(model_dir="/tmp/missing")
        assert tts.kokoro is None
        
        with pytest.raises(RuntimeError):
            await tts.speak("Fail")
