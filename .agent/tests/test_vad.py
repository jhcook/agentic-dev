
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys

# Mock onnxruntime in sys.modules BEFORE importing vad
mock_ort = MagicMock()
sys.modules["onnxruntime"] = mock_ort

from backend.voice.vad import VADProcessor

@pytest.fixture
def mock_onnx():
    # Setup mock_ort behavior
    mock_session = MagicMock()
    mock_ort.InferenceSession.return_value = mock_session
    mock_ort.SessionOptions.return_value = MagicMock()
    
    # Configure run output similar to previous
    def side_effect(output_names, input_feed):
        return [np.array([[0.9]]), np.zeros((2, 1, 128))]
    
    mock_session.run.side_effect = side_effect
    
    yield mock_session

def test_vad_initialization(mock_onnx):
    with patch("os.path.exists", return_value=True):
        processor = VADProcessor()
        assert processor.session is not None

def test_vad_process_speech(mock_onnx):
    with patch("os.path.exists", return_value=True):
        processor = VADProcessor()
        
        # Mock session.run to return high prob
        processor.session.run.return_value = [np.array([[0.8]]), np.zeros((2, 1, 128))]
        
        # 32ms of silence (512 samples)
        chunk = np.zeros(512, dtype=np.int16).tobytes()
        
        is_speech = processor.process(chunk)
        assert is_speech

def test_vad_process_silence(mock_onnx):
    with patch("os.path.exists", return_value=True):
        processor = VADProcessor()
        
        # Clear side_effect from fixture
        processor.session.run.side_effect = None
        # Mock session.run to return low prob
        processor.session.run.return_value = [np.array([[0.1]]), np.zeros((2, 1, 128))]
        
        chunk = np.zeros(512, dtype=np.int16).tobytes()
        
        is_speech = processor.process(chunk)
        assert not is_speech

def test_vad_short_chunk(mock_onnx):
    with patch("os.path.exists", return_value=True):
        processor = VADProcessor()
        
        # 10 samples (too short)
        chunk = np.zeros(10, dtype=np.int16).tobytes()
        
        is_speech = processor.process(chunk)
        assert is_speech is False
