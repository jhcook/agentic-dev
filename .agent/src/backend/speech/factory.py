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
from typing import Tuple, Dict, Type, Any

from .interfaces import STTProvider, TTSProvider, DisabledSTT, DisabledTTS
from agent.core.config import config
from agent.core.secrets import get_secret

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"deepgram", "deepgram_streaming", "whisper", "local", "google", "azure"}

_PROVIDERS: Dict[str, Type[Any]] = {}

def register_provider(name: str):
    def wrapper(cls):
        _PROVIDERS[name] = cls
        return cls
    return wrapper

def _get_voice_config() -> dict:
    """Load voice configuration from voice.yaml."""
    try:
        config_path = config.etc_dir / "voice.yaml"
        if config_path.exists():
            return config.load_yaml(config_path)
    except Exception as e:
        logger.warning(f"Failed to load voice.yaml: {e}")
    return {}

# --- Provider Implementations ---

@register_provider("deepgram")
class DeepgramProvider:
    def __init__(self, voice_config: dict):
        logger.info("Initializing Deepgram (file-based).")
        from .providers.deepgram import DeepgramSTT, DeepgramTTS
        api_key = get_secret("api_key", service="deepgram")
        
        if not api_key:
            logger.warning("DEEPGRAM_API_KEY is not set. Using Disabled providers.")
            self.stt = DisabledSTT()
            self.tts = DisabledTTS()
        else:
            self.stt = DeepgramSTT(api_key)
            self.tts = DeepgramTTS(api_key)

@register_provider("deepgram_streaming")
class DeepgramStreamingProvider:
    def __init__(self, voice_config: dict):
        logger.info("Initializing Deepgram (streaming WebSocket).")
        from .providers.deepgram_streaming import DeepgramStreamingSTT
        from .providers.deepgram import DeepgramTTS
        api_key = get_secret("api_key", service="deepgram")
        
        if not api_key:
            logger.warning("DEEPGRAM_API_KEY is not set. Using Disabled providers.")
            self.stt = DisabledSTT()
            self.tts = DisabledTTS()
        else:
            self.stt = DeepgramStreamingSTT(api_key)
            self.tts = DeepgramTTS(api_key)

try:
    from .providers import whisper
    from .providers import local
    
    @register_provider("local")
    @register_provider("whisper")
    class LocalProvider:
        def __init__(self, voice_config: dict):
            logger.info("Initializing Local/Whisper provider.")
            # STT
            try:
                model_size = config.get_value(voice_config, "whisper.model_size") or "base"
                device = config.get_value(voice_config, "whisper.device") or "auto"
                self.stt = whisper.FasterWhisperSTT(model_size=model_size, device=device)
            except Exception as e:
                logger.error(f"Failed to init Whisper STT: {e}")
                self.stt = DisabledSTT()
                
            # TTS
            try:
                self.tts = local.LocalTTS()
            except Exception as e:
                logger.error(f"Failed to init Local TTS: {e}")
                self.tts = DisabledTTS()

except (ImportError, Exception) as e:
    logger.debug(f"Local/Whisper providers not available: {e}")

try:
    from .providers import google
    
    @register_provider("google")
    class GoogleProvider:
        def __init__(self, voice_config: dict):
            logger.info("Initializing Google provider.")
            
            # Enforce Secret Manager usage
            # We support JSON content (preferred) or path (less secure but supported if user manually sets it in secrets? No, onboard only supports importing json content now)
            # Actually, onboard imports JSON content into 'application_credentials_json' secret.
            
            creds_json = get_secret("application_credentials_json", service="google")
            
            if not creds_json:
                logger.warning("Google Application Credentials not found in Secret Manager.")
                self.stt = DisabledSTT()
                self.tts = DisabledTTS()
            else:
                 self.stt = google.GoogleSTT(credentials_json=creds_json)
                 self.tts = google.GoogleTTS(credentials_json=creds_json)
            
except (ImportError, Exception) as e:
    logger.debug(f"Google provider not available: {e}")

try:
    from .providers import azure
    
    @register_provider("azure")
    class AzureProvider:
        def __init__(self, voice_config: dict):
            logger.info("Initializing Azure provider.")
            
            # Enforce Secret Manager usage
            key = get_secret("key", service="azure")
            # Region (Prioritize Secret, Fallback to Config for backward compatibility if any)
            region = get_secret("region", service="azure") or config.get_value(voice_config, "azure.region")
            
            if not key or not region:
                logger.warning("Azure credentials (key) or region not found in Secret Manager/Config.")
                self.stt = DisabledSTT()
                self.tts = DisabledTTS()
            else:
                self.stt = azure.AzureSTT(subscription_key=key, region=region)
                self.tts = azure.AzureTTS(subscription_key=key, region=region)

except (ImportError, Exception) as e:
    logger.debug(f"Azure provider not available: {e}")


@lru_cache(maxsize=1)
def get_voice_providers() -> Tuple[STTProvider, TTSProvider]:
    """
    Factory function to instantiate and return the configured voice providers.
    Reads configuration from .agent/etc/voice.yaml.
    
    Returns:
        A tuple containing the configured (STTProvider, TTSProvider).
    """
    voice_config = _get_voice_config()
    
    # We allow separate providers for STT and TTS, but for simplicity in this factory refactor
    # we assume the 'primary' provider set configures both, OR we mix and match.
    # The registry pattern maps "provider_name" -> "Class that inits both".
    # But if user wants STT=google and TTS=azure, this simple registry doesn't handle it easily unless
    # we instantiate two providers and pick parts.
    
    # Let's support mix-and-match by instantiation.
    
    stt_name = os.getenv(
        "VOICE_STT_PROVIDER",
        config.get_value(voice_config, "stt.provider") or "deepgram"
    ).lower()
    
    tts_name = os.getenv(
        "VOICE_TTS_PROVIDER",
        config.get_value(voice_config, "tts.provider") or "deepgram"
    ).lower()
    
    stt_provider = DisabledSTT()
    tts_provider = DisabledTTS()
    
    # helper to get instance
    cache = {}

    def get_instance(name):
        if name in cache: return cache[name]
        if name in _PROVIDERS:
            try:
                instance = _PROVIDERS[name](voice_config)
                cache[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to instantiate provider {name}: {e}")
                return None
        return None

    # STT
    inst = get_instance(stt_name)
    if inst:
        stt_provider = inst.stt
    else:
        logger.warning(f"STT Provider '{stt_name}' not found or failed.")

    # TTS
    # If same name, reuse instance
    inst = get_instance(tts_name)
    if inst:
        tts_provider = inst.tts
    else:
        logger.warning(f"TTS Provider '{tts_name}' not found or failed.")
        
    return stt_provider, tts_provider
