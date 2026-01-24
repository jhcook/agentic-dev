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
from functools import lru_cache
from typing import Tuple

from .interfaces import STTProvider, TTSProvider
from agent.core.config import config

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"deepgram", "deepgram_streaming", "whisper", "local"}

def _get_voice_config() -> dict:
    """Load voice configuration from voice.yaml."""
    try:
        config_path = config.etc_dir / "voice.yaml"
        if config_path.exists():
            return config.load_yaml(config_path)
    except Exception as e:
        logger.warning(f"Failed to load voice.yaml: {e}")
    return {}

@lru_cache(maxsize=1)
def get_voice_providers() -> Tuple[STTProvider, TTSProvider]:
    """
    Factory function to instantiate and return the configured voice providers.
    Reads configuration from .agent/etc/voice.yaml.
    
    Configuration priority:
        1. Environment variables (VOICE_STT_PROVIDER, VOICE_TTS_PROVIDER)
        2. voice.yaml config file
        3. Defaults (deepgram for both)
    
    Returns:
        A tuple containing the configured (STTProvider, TTSProvider).
    """
    from .interfaces import DisabledSTT, DisabledTTS
    
    voice_config = _get_voice_config()
    stt_provider = DisabledSTT()
    tts_provider = DisabledTTS()
    
    # Get STT provider (env var > config > default)
    stt_provider_name = os.getenv(
        "VOICE_STT_PROVIDER",
        config.get_value(voice_config, "stt.provider") or "deepgram"
    ).lower()
    
    # Get TTS provider (env var > config > default)
    tts_provider_name = os.getenv(
        "VOICE_TTS_PROVIDER",
        config.get_value(voice_config, "tts.provider") or "deepgram"
    ).lower()

    # Initialize STT Provider
    try:
        if stt_provider_name == "deepgram":
            logger.info("Initializing Deepgram STT (file-based).")
            from .providers.deepgram import DeepgramSTT
            from agent.core.secrets import get_secret
            api_key = get_secret("api_key", service="deepgram")
            if not api_key:
                logger.warning("DEEPGRAM_API_KEY is not set. STT will be disabled.")
            else:
                stt_provider = DeepgramSTT(api_key)
        
        elif stt_provider_name == "deepgram_streaming":
            logger.info("Initializing Deepgram STT (streaming WebSocket).")
            from .providers.deepgram_streaming import DeepgramStreamingSTT
            from agent.core.secrets import get_secret
            api_key = get_secret("api_key", service="deepgram")
            if not api_key:
                logger.warning("DEEPGRAM_API_KEY is not set. Streaming STT will be disabled.")
            else:
                stt_provider = DeepgramStreamingSTT(api_key)
        
        elif stt_provider_name in ["whisper", "local"]:
            logger.info("Initializing faster-whisper STT (offline).")
            from .providers.whisper import FasterWhisperSTT
            model_size = config.get_value(voice_config, "whisper.model_size") or "base"
            device = config.get_value(voice_config, "whisper.device") or "auto"
            stt_provider = FasterWhisperSTT(model_size=model_size, device=device)
        else:
             logger.warning(f"Unsupported STT provider: {stt_provider_name}")
    except (ImportError, Exception) as e:
        logger.error(f"Failed to initialize STT provider '{stt_provider_name}': {e}")

    # Initialize TTS Provider
    try:
        if tts_provider_name in ["deepgram", "deepgram_streaming"]:
            logger.info("Initializing Deepgram TTS.")
            from .providers.deepgram import DeepgramTTS
            from agent.core.secrets import get_secret
            api_key = get_secret("api_key", service="deepgram")
            if not api_key:
                logger.warning("DEEPGRAM_API_KEY is not set. TTS will be disabled.")
            else:
                tts_provider = DeepgramTTS(api_key)
        
        elif tts_provider_name in ["local", "whisper"]:
            logger.info("Initializing Local TTS (Kokoro).")
            from .providers.local import LocalTTS
            tts_provider = LocalTTS()
        else:
             logger.warning(f"Unsupported TTS provider: {tts_provider_name}")
    except (ImportError, Exception) as e:
        logger.error(f"Failed to initialize TTS provider '{tts_provider_name}': {e}")

    return stt_provider, tts_provider
