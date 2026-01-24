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

"""Faster-whisper offline STT provider."""

import asyncio
import logging
import numpy as np
from typing import AsyncGenerator, Optional

from backend.speech.interfaces import STTProvider

logger = logging.getLogger(__name__)


class FasterWhisperSTT(STTProvider):
    """Offline STT using faster-whisper (local inference)."""
    
    def __init__(self, model_size: str = "base", device: str = "auto"):
        """
        Initialize faster-whisper STT.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large)
            device: Device to run on (cpu, cuda, auto)
        """
        self.model_size = model_size
        self.device = device
        self.model: Optional["WhisperModel"] = None
        self.provider_name = "faster_whisper"
        self._initialize_model()
    
    def _initialize_model(self):
        """Lazy load faster-whisper model."""
        try:
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading faster-whisper model ({self.model_size})...")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8"  # Optimize for speed
            )
            logger.info("Faster-whisper model loaded successfully")
        except ImportError:
            logger.error(
                "faster-whisper not installed. "
                "Run: pip install faster-whisper"
            )
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            self.model = None
    
    async def listen(self, audio_data: bytes) -> str:
        """
        Transcribe audio bytes (batch mode).
        
        Args:
            audio_data: Raw PCM audio (Int16, 16kHz, mono)
            
        Returns:
            Transcribed text
        """
        if not self.model:
            raise RuntimeError("Faster-whisper model not initialized")
        
        # Convert bytes to numpy array (Int16 -> Float32)
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Run transcription in thread pool
        segments, info = await asyncio.to_thread(
            self.model.transcribe,
            audio_np,
            language="en",
            beam_size=1,  # Faster inference
            vad_filter=True,  # Voice activity detection
        )
        
        # Combine segments
        transcript = " ".join(segment.text for segment in segments)
        return transcript.strip()
    
    async def stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        Streaming mode: accumulate chunks and transcribe in batches.
        
        Faster-whisper doesn't support true streaming, so we accumulate
        audio and transcribe when we have enough (~1-2 seconds).
        """
        buffer = bytearray()
        sample_rate = 16000
        bytes_per_sample = 2  # Int16
        chunk_duration_s = 1.5  # Process every 1.5 seconds
        chunk_size = int(chunk_duration_s * sample_rate * bytes_per_sample)
        
        async for chunk in audio_stream:
            buffer.extend(chunk)
            
            # Process when we have enough audio
            if len(buffer) >= chunk_size:
                audio_data = bytes(buffer[:chunk_size])
                buffer = buffer[chunk_size:]  # Keep remainder
                
                transcript = await self.listen(audio_data)
                if transcript:
                    yield transcript
        
        # Process remaining audio
        if buffer:
            transcript = await self.listen(bytes(buffer))
            if transcript:
                yield transcript
    
    async def health_check(self) -> bool:
        """Check if model is loaded."""
        return self.model is not None
