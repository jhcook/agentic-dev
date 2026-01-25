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


import os
import logging
import numpy as np
import urllib.request

logger = logging.getLogger(__name__)

class VADProcessor:
    """
    Voice Activity Detection using Silero VAD (ONNX).
    """
    def __init__(self, model_path: str = None, threshold: float = 0.5, sampling_rate: int = 16000, min_speech_duration_ms: int = 250): # Threshold 0.5 (Echo resistant), Duration 250ms
        if model_path is None:
            try:
                from agent.core.config import config
                model_path = str(config.storage_dir / "silero_vad.onnx")
            except Exception as e:
                print(f"Config import failed: {e}")
                model_path = ".agent/storage/silero_vad.onnx"
        self.model_path = model_path
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.session = None
        self.ort = None # Module reference
        # Silero V4/V5 state shape is (2, 1, 128)
        self._h = np.zeros((2, 1, 128)).astype('float32')
        self._c = np.zeros((2, 1, 128)).astype('float32') # Unused in v4/v5 but kept for compat just in case
        
        self.initialize()

    def initialize(self):
        """Downloads model if missing and initializes ONNX session."""
        try:
            import onnxruntime as ort
            self.ort = ort
        except ImportError:
            print("onnxruntime not available. VAD disabled.")
            return

        if not os.path.exists(self.model_path):
            print(f"Downloading Silero VAD model to {self.model_path}...")
            # Updated URL - the model is in the releases
            url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
            try:
                urllib.request.urlretrieve(url, self.model_path)
                print("Download complete.")
            except Exception as e:
                print(f"Failed to download VAD model: {e}. VAD will be disabled.")
                return  # Don't raise, just disable VAD

        try:
            # Suppress excessive ONNX warnings
            sess_options = self.ort.SessionOptions()
            sess_options.log_severity_level = 3
            self.session = self.ort.InferenceSession(self.model_path, sess_options)
        except Exception as e:
            print(f"Failed to initialize VAD session: {e}")
            raise

    def process(self, audio_chunk: bytes) -> bool:
        """
        Process a chunk of audio.
        Chunk should be 16-bit PCM mono.
        Iterates over the chunk in 512-sample windows to maintain VAD state.
        """
        if not self.session:
            return False

        # Convert bytes to float32 numpy array
        # Assuming 16-bit PCM input
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        window_size = 512
        speech_detected = False
        
        # Iterate over the buffer to update state continuously
        for i in range(0, len(audio_float32), window_size):
            chunk = audio_float32[i:i + window_size]
            
            # Pad valid small chunks
            if len(chunk) < window_size:
                chunk = np.pad(chunk, (0, window_size - len(chunk)))
            
            # Add batch dimension: [1, 512]
            x = chunk[np.newaxis, :]
            
            # Prepare inputs for V4/V5
            sr = np.array([self.sampling_rate], dtype=np.int64)
            
            ort_inputs = {
                'input': x,
                'state': self._h,
                'sr': sr
            }
            
            outs = self.session.run(None, ort_inputs)
            out = outs[0]
            self._h = outs[1]
            
            # Probability is in out
            prob = out[0][0]
            
            if prob > self.threshold:
                speech_detected = True
        
        return speech_detected

    def reset(self):
        """Reset validation state."""
        self._h = np.zeros((2, 1, 128)).astype('float32')
