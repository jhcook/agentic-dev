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

# Allow numpy to load pickled data (required for Kokoro voices.json)
import os
os.environ['NPY_ALLOW_PICKLE'] = '1'

import logging
import asyncio
import scipy.signal
import soundfile as sf
import io
from pathlib import Path
from kokoro_onnx import Kokoro
from agent.core.config import config

logger = logging.getLogger(__name__)

# Constants
TARGET_SAMPLE_RATE = 16000
DEFAULT_VOICE = "af_sarah" # Default voice for Kokoro

class LocalTTS:
    """
    Local Text-to-Speech provider using Kokoro (ONNX).
    Implements TTSProvider protocol.
    """
    
    def __init__(self, model_dir: str = None):
        """
        Initialize LocalTTS.
        
        Args:
            model_dir: Directory containing kokoro-v0_19.onnx and voices.json.
                       Defaults to .agent/models/kokoro
        """
        if model_dir:
            self.model_dir = Path(model_dir)
        else:
            self.model_dir = config.agent_dir / "models" / "kokoro"
            
        self.onnx_path = self.model_dir / "kokoro-v0_19.onnx"
        self.voices_path = self.model_dir / "voices.json"
        
        self.kokoro = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize Kokoro model if files exist."""
        if not self.onnx_path.exists() or not self.voices_path.exists():
            logger.warning(
                f"Kokoro model files not found at {self.model_dir}. "
                "Local TTS will verify_health=False until download."
            )
            return

        try:
            logger.info(f"Loading Kokoro model from {self.model_dir}...")
            self.kokoro = Kokoro(str(self.onnx_path), str(self.voices_path))
            logger.info("Kokoro model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Kokoro model: {e}")
            self.kokoro = None

    async def speak(self, text: str) -> bytes:
        """
        Convert text to audio bytes (16kHz WAV).
        """
        if not self.kokoro:
            raise RuntimeError("Kokoro model not initialized. Run download_models.py first.")

        # Run synthesis in thread pool to avoid blocking event loop
        # kokoro.create returns (samples, sample_rate)
        # samples is a numpy array (float32)
        try:
            samples, source_sr = await asyncio.to_thread(
                self.kokoro.create,
                text,
                voice=DEFAULT_VOICE,
                speed=1.0,
                lang="en-us"
            )
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}")
            raise

        # Resample if needed
        if source_sr != TARGET_SAMPLE_RATE:
            num_samples = int(len(samples) * TARGET_SAMPLE_RATE / source_sr)
            samples = await asyncio.to_thread(
                scipy.signal.resample, samples, num_samples
            )
        
        # Convert to WAV bytes
        # soundfile expects numpy array
        buffer = io.BytesIO()
        sf.write(buffer, samples, TARGET_SAMPLE_RATE, format='WAV')
        return buffer.getvalue()

    async def health_check(self) -> bool:
        """Check if model is loaded."""
        return self.kokoro is not None
