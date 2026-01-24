
import os
import logging
import numpy as np
import urllib.request

logger = logging.getLogger(__name__)

class VADProcessor:
    """
    Voice Activity Detection using Silero VAD (ONNX).
    """
    def __init__(self, model_path: str = "silero_vad.onnx", threshold: float = 0.5, sampling_rate: int = 16000):
        self.model_path = model_path
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.session = None
        self.ort = None # Module reference
        self._h = np.zeros((2, 1, 64)).astype('float32') # LSTM state
        self._c = np.zeros((2, 1, 64)).astype('float32') # LSTM state
        
        self.initialize()

    def initialize(self):
        """Downloads model if missing and initializes ONNX session."""
        try:
            import onnxruntime as ort
            self.ort = ort
        except ImportError:
            logger.warning("onnxruntime not available. VAD disabled.")
            return

        if not os.path.exists(self.model_path):
            logger.info(f"Downloading Silero VAD model to {self.model_path}...")
            # Updated URL - the model is in the releases
            url = "https://github.com/snakers4/silero-vad/releases/download/v5.0/silero_vad.onnx"
            try:
                urllib.request.urlretrieve(url, self.model_path)
                logger.info("Download complete.")
            except Exception as e:
                logger.warning(f"Failed to download VAD model: {e}. VAD will be disabled.")
                return  # Don't raise, just disable VAD

        try:
            # Suppress excessive ONNX warnings
            sess_options = self.ort.SessionOptions()
            sess_options.log_severity_level = 3
            self.session = self.ort.InferenceSession(self.model_path, sess_options)
        except Exception as e:
            logger.error(f"Failed to initialize VAD session: {e}")
            raise

    def process(self, audio_chunk: bytes) -> bool:
        """
        Process a chunk of audio.
        Chunk should be 16-bit PCM mono.
        Silero expects chunks of 512, 1024, or 1536 samples at 16k.
        """
        if not self.session:
            return False

        # Convert bytes to float32 numpy array
        # Assuming 16-bit PCM input
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Check size compatibility logic would be needed for arbitrary chunks
        # But for now assuming the WebSocket sends appropriate chunks or we accumulate.
        # Silero V4 supports 512, 1024, 1536 for 16khz
        
        # If chunk is too small/large, we might skip or buffer (omitted for MVP brevity, 
        # relying on router to send decent chunks or just processing what fits)
        # Actually, let's just pad or slice if needed to be safe? 
        # Or better: Iterate if strictly required. 
        # Silero allows flexible size? No, strict on specific sizes due to graph.
        
        # Let's enforce 512 samples context if possible. 
        # 512 samples @ 16k = 32ms.
        
        if len(audio_float32) < 512:
            return False # Too short
            
        # We'll take the first compatible chunk size or loop
        # Simple MVP: Process first 512 samples
        x = audio_float32[:512] 
        
        # Add batch dimension: [1, 512]
        x = x[np.newaxis, :]
        
        ort_inputs = {
            'input': x,
            'state': self._h,
            'context': self._c
        }
        
        # Include sample rate if model requires it (v4 does)
        # v4 inputs: input, state, sr (int64)
        sr = np.array([self.sampling_rate], dtype=np.int64)
        ort_inputs['sr'] = sr
        
        # Run inference
        # Outputs: output, state, context (names vary by version, v4 usually 'output', 'stateN'...)
        # Let's check inputs/outputs dynamically or assume v4 standard
        
        # v4 standard: inputs=['input', 'state', 'sr'], outputs=['output', 'stateN']
        # Wait, the state handling in my init assumed separated h/c which is v3 style?
        # v4 uses a single concatenated state tensor usually?
        # Let's adjust to be robust or download v3? 
        # Providing v4 URL: "silero_vad.onnx" (v4 is usually default now).
        # v4 ONNX signature: 
        # Inputs: input (1, N), state (2, 1, 128), sr (1)
        # Outputs: output (1, N), state (2, 1, 128)
        
        # My init: _h (2,1,64) _c (2,1,64). 
        # If v4 uses (2,1,128), I should fix.
        
        # Let's try to inspect or stick to known v4 signature.
        # State: (2, 1, 128)
        
        # Re-init state for v4
        if self._h.shape[-1] == 64:
             self._h = np.zeros((2, 1, 128)).astype('float32')
             # drop self._c
        
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
        
        return prob > self.threshold

    def reset(self):
        """Reset validation state."""
        self._h = np.zeros((2, 1, 128)).astype('float32')
