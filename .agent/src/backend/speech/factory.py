import os
import logging
from functools import lru_cache
from typing import Tuple

from .interfaces import STTProvider, TTSProvider
from .providers.deepgram import DeepgramSTT, DeepgramTTS, ConfigurationError

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"deepgram"}

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
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            logger.error("DEEPGRAM_API_KEY environment variable not set.")
            raise ConfigurationError("DEEPGRAM_API_KEY is required for the 'deepgram' provider.")
        
        stt_provider = DeepgramSTT(api_key)
        tts_provider = DeepgramTTS(api_key)
        return stt_provider, tts_provider
        
    # This block is unreachable with current logic but is good for future expansion
    # In a real scenario, you'd add more 'elif' blocks here.
    raise NotImplementedError(f"Provider '{provider_name}' is not implemented.")
