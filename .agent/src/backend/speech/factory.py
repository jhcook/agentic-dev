import os
import logging
from functools import lru_cache
from typing import Tuple

from .interfaces import STTProvider, TTSProvider
from .providers.deepgram import DeepgramSTT, DeepgramTTS, ConfigurationError

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"deepgram", "local"}

@lru_cache(maxsize=1)
def get_voice_providers() -> Tuple[STTProvider, TTSProvider]:
    """
    Factory function to instantiate and return the configured voice providers.
    Reads configuration from environment variables.
    
    Raises:
        ConfigurationError: If the provider is unsupported or misconfigured.
        
    Returns:
        A tuple containing the configured (STTProvider, TTSProvider).
    """
    provider_name = os.getenv("VOICE_PROVIDER", "deepgram").lower()
    
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ConfigurationError(f"Unsupported voice provider: {provider_name}")

    if provider_name == "deepgram":
        logger.info("Initializing Deepgram voice providers.")
        # Use SecretManager to retrieve key (try keychain -> secret store -> env)
        from agent.core.secrets import get_secret
        api_key = get_secret("api_key", "deepgram")
        if not api_key:
            logger.error("DEEPGRAM_API_KEY environment variable not set.")
            raise ConfigurationError("DEEPGRAM_API_KEY is required for the 'deepgram' provider.")
        
        stt_provider = DeepgramSTT(api_key)
        tts_provider = DeepgramTTS(api_key)
        return stt_provider, tts_provider
    
    elif provider_name == "local":
        logger.info("Initializing Local voice providers (Kokoro TTS + Deepgram STT fallback).")
        from .providers.local import LocalTTS
        
        # Fallback STT to Deepgram for now (INFRA-030 is TTS focused)
        from agent.core.secrets import get_secret
        api_key = get_secret("api_key", "deepgram")
        if not api_key:
             logger.warning("Deepgram API key missing. STT will fail if used.")
             # We can likely return a dummy STT or raise error if STT is strictly required
             # For now, let's assume user has key or doesn't use STT in this specific test
        
        # Initialize LocalTTS
        tts_provider = LocalTTS()
        
        # Initialize DeepgramSTT (or Dummy if we wanted strictly offline, but we need an implementation)
        stt_provider = DeepgramSTT(api_key) if api_key else None 
        # Wait, returning None violates type hint. 
        # Let's trust they have Deepgram key or modify type hint.
        # Ideally we'd have LocalSTT (Faster-Whisper) here soon.
        
        if stt_provider is None:
             raise ConfigurationError("Local STT not yet implemented and Deepgram key missing.")

        return stt_provider, tts_provider

    raise NotImplementedError(f"Provider '{provider_name}' is not implemented.")
