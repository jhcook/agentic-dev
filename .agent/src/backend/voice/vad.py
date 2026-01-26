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
import hashlib
import time
import requests
import numpy as np
from typing import Optional

# Try importing prometheus_client, handle if missing (though it should be present)
try:
    from prometheus_client import Counter, Histogram
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default URL, overridable by environment variable for configurability
SILERO_MODEL_URL = os.getenv(
    "SILERO_MODEL_URL", 
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
SILERO_MODEL_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
DOWNLOAD_RETRIES = 3
DOWNLOAD_BACKOFF_FACTOR = 2

# Metrics Definitions
if METRICS_AVAILABLE:
    VAD_INIT_TIME = Histogram('vad_initialization_duration_seconds', 'Time spent initializing VAD')
    VAD_PROCESSING_TIME = Histogram('vad_processing_latency_seconds', 'Time spent processing audio chunk', ['implementation'])
    VAD_FALLBACK_COUNT = Counter('vad_fallback_total', 'Count of fallbacks to WebRTC')
    VAD_DOWNLOAD_COUNT = Counter('vad_model_download_total', 'Count of model download attempts', ['status'])
    VAD_INIT_COUNT = Counter('vad_initialization_total', 'Count of VAD initializations', ['implementation'])

class VADProcessor:
    """
    Hybrid Voice Activity Detection Processor.
    
    This class implements a resilient VAD strategy:
    1. Attempts to use Silero VAD (ONNX) as the primary engine for high accuracy.
    2. Automatically falls back to Google's WebRTC VAD if Silero fails to initialize 
       (e.g., missing dependencies, download failure, integrity check failure).
    """
    def __init__(self, aggressiveness: int = 1, sample_rate: int = 16000, threshold: float = 0.5):
        """
        Initialize the VAD Processor.

        Args:
            aggressiveness (int): WebRTC VAD aggressiveness (0-3). Higher is more aggressive in filtering non-speech.
            sample_rate (int): Audio sample rate in Hz. Default 16000.
            threshold (float): Silero VAD probability threshold (0.0-1.0). Default 0.5.
        """
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.threshold = threshold
        
        # State for Silero
        self.silero_session = None
        self._h = np.zeros((2, 1, 128)).astype('float32')
        self.model_path = None
        
        # State for WebRTC
        self.webrtc_vad = None
        self.webrtc_buffer = bytearray()
        self.frame_duration_ms = 20
        self.frame_size_bytes = int(sample_rate * (self.frame_duration_ms / 1000.0) * 2)
        
        start_time = time.time()
        self._initialize()
        duration = time.time() - start_time
        
        if METRICS_AVAILABLE:
            VAD_INIT_TIME.observe(duration)
            
        logger.info(f"event='vad_initialized' duration_ms={duration*1000:.2f}")

    def _initialize(self):
        """Initialize VAD implementations, preferring Silero."""
        if self._try_initialize_silero():
            logger.info("event='vad_selected' implementation='silero' status='success'")
            if METRICS_AVAILABLE:
                VAD_INIT_COUNT.labels(implementation='silero').inc()
            return

        if self._try_initialize_webrtc():
             logger.info("event='vad_selected' implementation='webrtc' status='fallback'")
             if METRICS_AVAILABLE:
                VAD_INIT_COUNT.labels(implementation='webrtc').inc()
                VAD_FALLBACK_COUNT.inc()
             return
             
        logger.error("event='vad_initialization_failed' status='critical'")

    def _try_initialize_silero(self) -> bool:
        """Attempt to initialize Silero VAD (ONNX)."""
        try:
            import onnxruntime as ort
            from agent.core.config import config
            
            self.model_path = str(config.storage_dir / "silero_vad.onnx")
            
            if not self._download_and_verify_model(self.model_path):
                return False
            
            sess_options = ort.SessionOptions()
            sess_options.log_severity_level = 3
            self.silero_session = ort.InferenceSession(self.model_path, sess_options)
            return True
        except Exception as e:
            logger.warning(f"event='silero_init_failed' error='{e}' action='fallback'")
            return False

    def _download_and_verify_model(self, path: str) -> bool:
        """
        Downloads model with backoff and strict permissions.
        
        Args:
            path (str): Local path to store the model.
            
        Returns:
            bool: True if model is available and verified, False otherwise.
        """
        try:
            # Check if file exists
            if os.path.exists(path):
                if self._verify_checksum(path):
                    return True
                logger.warning("event='model_validation_failed' action='redownload'")
                os.remove(path)
            
            # Download with retries and backoff
            logger.info(f"event='downloading_model' path='{path}'")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            for attempt in range(DOWNLOAD_RETRIES):
                try:
                    response = requests.get(SILERO_MODEL_URL, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    with open(path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Set strict permissions (read/write by owner only)
                    os.chmod(path, 0o600)
                    
                    if self._verify_checksum(path):
                        logger.info("event='model_verified' status='success'")
                        if METRICS_AVAILABLE:
                            VAD_DOWNLOAD_COUNT.labels(status='success').inc()
                        return True
                    else:
                         logger.error(f"event='integrity_check_failed' attempt={attempt + 1}")
                         
                except Exception as e:
                    logger.warning(f"event='download_failed' attempt={attempt + 1} error='{e}'")
                
                # Exponential backoff
                if attempt < DOWNLOAD_RETRIES - 1:
                    sleep_time = DOWNLOAD_BACKOFF_FACTOR ** attempt
                    time.sleep(sleep_time)
            
            # Cleanup if failed
            if os.path.exists(path):
                 os.remove(path)
            
            if METRICS_AVAILABLE:
                VAD_DOWNLOAD_COUNT.labels(status='failure').inc()
            return False
            
        except Exception as e:
            logger.error(f"event='model_download_error' error='{e}'")
            if METRICS_AVAILABLE:
                VAD_DOWNLOAD_COUNT.labels(status='failure').inc()
            return False

    def _verify_checksum(self, path: str) -> bool:
        """Verify SHA256 checksum of the file."""
        try:
            sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            
            calculated_hash = sha256.hexdigest()
            if calculated_hash != SILERO_MODEL_SHA256:
                logger.error(f"event='checksum_mismatch' expected='{SILERO_MODEL_SHA256}' got='{calculated_hash}'")
                return False
            return True
        except Exception as e:
            logger.error(f"event='checksum_verification_error' error='{e}'")
            return False

    def _try_initialize_webrtc(self) -> bool:
        """Attempt to initialize WebRTC VAD."""
        try:
            import webrtcvad
            self.webrtc_vad = webrtcvad.Vad(self.aggressiveness)
            return True
        except Exception as e:
            logger.error(f"event='webrtc_init_failed' error='{e}'")
            return False

    def process(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk for speech detection.
        
        Args:
            audio_chunk (bytes): Raw PCM audio data (16-bit mono).
            
        Returns:
            bool: True if speech is detected using the active engine.
        """
        start_time = time.time()
        result = False
        impl = 'unknown'
        
        if self.silero_session:
            result = self._process_silero(audio_chunk)
            impl = 'silero'
        elif self.webrtc_vad:
            result = self._process_webrtc(audio_chunk)
            impl = 'webrtc'
            
        # Observability: Log latency metrics
        if METRICS_AVAILABLE:
            duration = time.time() - start_time
            VAD_PROCESSING_TIME.labels(implementation=impl).observe(duration)
             
        return result

    def _process_silero(self, audio_chunk: bytes) -> bool:
        """Silero-specific processing logic."""
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        window_size = 512
        speech_detected = False
        
        for i in range(0, len(audio_float32), window_size):
            chunk = audio_float32[i:i + window_size]
            if len(chunk) < window_size:
                chunk = np.pad(chunk, (0, window_size - len(chunk)))
            
            x = chunk[np.newaxis, :]
            sr = np.array([self.sample_rate], dtype=np.int64)
            
            ort_inputs = {
                'input': x,
                'state': self._h,
                'sr': sr
            }
            
            outs = self.silero_session.run(None, ort_inputs)
            self._h = outs[1]
            prob = outs[0][0][0]
            
            if prob > self.threshold:
                speech_detected = True
        
        return speech_detected

    def _process_webrtc(self, audio_chunk: bytes) -> bool:
        """WebRTC-specific processing logic."""
        self.webrtc_buffer.extend(audio_chunk)
        speech_found = False
        
        while len(self.webrtc_buffer) >= self.frame_size_bytes:
            frame = bytes(self.webrtc_buffer[:self.frame_size_bytes])
            del self.webrtc_buffer[:self.frame_size_bytes]
            
            try:
                if self.webrtc_vad.is_speech(frame, self.sample_rate):
                    speech_found = True
            except Exception as e:
                logger.error(f"event='webrtc_processing_error' error='{e}'")
                
        return speech_found

    def reset(self):
        """Reset VAD state."""
        if self.silero_session:
            self._h = np.zeros((2, 1, 128)).astype('float32')
        if self.webrtc_vad:
            self.webrtc_buffer.clear()
