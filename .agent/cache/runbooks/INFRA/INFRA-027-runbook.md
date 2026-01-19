# INFRA-027: Core Voice Abstractions & Deepgram

## State
ACCEPTED

## Goal Description
To establish a provider-agnostic voice architecture by defining `STTProvider` and `TTSProvider` interfaces. This change introduces a concrete implementation for Deepgram, loaded via a factory, ensuring that the core application logic is decoupled from specific vendor SDKs.

## Panel Review Findings
- **@Architect**: The proposed abstraction-based approach using interfaces (`STTProvider`, `TTSProvider`) and a factory pattern is sound. It directly implements the principles outlined in ADR-007 for modular, extensible services. This design correctly isolates vendor-specific code within dedicated provider modules, preventing SDK bleed into core business logic. The use of `async` methods is appropriate for I/O-bound operations like API calls. The factory provides a single point of control for dependency injection, simplifying configuration and future provider-switching.

- **@Security**: The primary concern is the handling of the Deepgram API key. The requirement to use a `SecretManager` or environment variables is correct. The implementation MUST NOT allow the key to be hardcoded or logged. The service MUST fail on startup (fail-closed) if the API key is not configured; this prevents running in an insecure or non-functional state. The Deepgram client should be configured with a reasonable timeout to prevent resource exhaustion attacks or hangs. Ensure the `deepgram-sdk` dependency is vetted for known vulnerabilities.

- **@QA**: The test strategy is well-defined but needs specifics. We must use a library like `respx` to mock the HTTP requests made by the `deepgram-sdk`, ensuring tests are fast, reliable, and don't rely on network access or a valid API key. Test cases must explicitly cover:
    1.  Successful STT/TTS calls.
    2.  Graceful handling of API errors from Deepgram (e.g., 401 Unauthorized, 500 Server Error).
    3.  The `ConfigurationError` when the API key is missing.
    4.  An `isinstance()` check in a dedicated test to formally verify that `DeepgramSTT` and `DeepgramTTS` correctly implement their respective provider interfaces.

- **@Docs**: The new interfaces (`STTProvider`, `TTSProvider`) must be thoroughly documented with docstrings explaining their purpose, methods, parameters, and return types. The `DeepgramSTT`/`TTS` implementations should also have class and method docstrings. A new `README.md` file should be created in the `backend/speech/` directory explaining the provider architecture and how to add a new provider in the future. The `CHANGELOG.md` must be updated to reflect this significant architectural addition.

- **@Compliance**: This change is internal architecture and does not alter any external API contracts; therefore, it does not violate the `api-contract-validation.mdc` rule. The implementation correctly adheres to `ADR-007` by creating a decoupled service layer. From a data privacy perspective, ensure that any audio data passed to Deepgram is handled according to our data processing agreements and that no Personally Identifiable Information (PII) is inadvertently logged during the process. This aligns with our commitment to privacy.

- **@Observability**: This is a critical integration point that requires robust monitoring.
    - **Logging**: All logs originating from the speech module must be structured (JSON). They should include a `provider` field (e.g., `provider: "deepgram"`) to allow for easy filtering. Logs must be scrubbed of sensitive data, especially API keys. Error logs for failed API calls must include a unique request ID and error details from the provider.
    - **Metrics**: Implement Prometheus/StatsD metrics for:
        - `voice_provider_requests_total{provider="deepgram", type="stt|tts", status="success|error"}`: A counter for tracking requests.
        - `voice_provider_request_duration_seconds{provider="deepgram", type="stt|tts"}`: A histogram to measure the latency of API calls.

## Implementation Steps
### [backend]
#### NEW `backend/speech/interfaces.py`
- Create new, pure interfaces for voice services. These MUST NOT import `deepgram` or any other vendor SDK.

```python
# backend/speech/interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

# Using Protocol for structural subtyping, which is more flexible.
@runtime_checkable
class STTProvider(Protocol):
    """
    Interface for a Speech-to-Text (STT) provider.
    """
    @abstractmethod
    async def listen(self, audio_data: bytes) -> str:
        """
        Transcribes the given audio data into text.

        Args:
            audio_data: The raw byte content of the audio.

        Returns:
            The transcribed text.
        """
        ...

@runtime_checkable
class TTSProvider(Protocol):
    """
    Interface for a Text-to-Speech (TTS) provider.
    """
    @abstractmethod
    async def speak(self, text: str) -> bytes:
        """
        Synthesizes the given text into audio.

        Args:
            text: The text to be synthesized.

        Returns:
            The raw byte content of the generated audio.
        """
        ...
```

#### NEW `backend/speech/providers/__init__.py`
- Create an empty `__init__.py` to make `providers` a package.

#### NEW `backend/speech/providers/deepgram.py`
- Create the concrete implementation for Deepgram services.

```python
# backend/speech/providers/deepgram.py
import os
import logging
from deepgram import DeepgramClient, PrerecordedOptions, SpeakOptions

from backend.speech.interfaces import STTProvider, TTSProvider

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    pass

class DeepgramSTT(STTProvider):
    """Deepgram implementation for Speech-to-Text."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ConfigurationError("Deepgram API key is not configured.")
        self.client = DeepgramClient(api_key)

    async def listen(self, audio_data: bytes) -> str:
        source = {"buffer": audio_data}
        options = PrerecordedOptions(model="nova-2", smart_format=True)
        
        logger.info("Sending STT request to Deepgram.")
        response = await self.client.listen.prerecorded.v("1").send(source, options)
        
        # Best-effort transcription selection
        transcript = response.results.channels[0].alternatives[0].transcript
        logger.info("Received STT response from Deepgram.")
        return transcript

class DeepgramTTS(TTSProvider):
    """Deepgram implementation for Text-to-Speech."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ConfigurationError("Deepgram API key is not configured.")
        self.client = DeepgramClient(api_key)

    async def speak(self, text: str) -> bytes:
        options = SpeakOptions(model="aura-asteria-en")
        source = {"text": text}
        
        logger.info("Sending TTS request to Deepgram.")
        response = await self.client.speak.v("1").stream(source, options)
        
        # The response object from the SDK can be directly read for its bytes
        logger.info("Received TTS response from Deepgram.")
        return response.stream.getvalue()
```

#### NEW `backend/speech/factory.py`
- Create a factory to build and return the configured voice provider.

```python
# backend/speech/factory.py
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

```

#### MODIFY `pyproject.toml`
- Add the new `deepgram-sdk` and `respx` dependencies to the `project.dependencies` list.
```toml
# In pyproject.toml [project] dependencies
dependencies = [
    # ... existing dependencies ...
    "deepgram-sdk>=3.0",
    "respx>=0.20.0",
]
```

## Verification Plan
### Automated Tests
- [ ] **Test Interface Purity**: Create a test that imports `backend.speech.interfaces` and asserts that `sys.modules` does not contain `deepgram`, proving no vendor SDKs are leaked into the abstractions.
- [ ] **Test Factory Configuration**:
    - [ ] Verify `get_voice_providers` returns `DeepgramSTT` and `DeepgramTTS` instances when `VOICE_PROVIDER` is "deepgram".
    - [ ] Verify `get_voice_providers` raises `ConfigurationError` if `DEEPGRAM_API_KEY` is not set.
    - [ ] Verify `get_voice_providers` raises `ConfigurationError` if `VOICE_PROVIDER` is set to an unsupported value.
- [ ] **Test Deepgram Provider (STT)**:
    - [ ] Using `respx`, mock a successful Deepgram STT API response and assert `DeepgramSTT.listen` returns the correct transcript.
    - [ ] Mock a Deepgram API error (e.g., 401) and assert that the `DeepgramSTT.listen` method raises the appropriate exception from the SDK.
- [ ] **Test Deepgram Provider (TTS)**:
    - [ ] Using `respx`, mock a successful Deepgram TTS API response and assert `DeepgramTTS.speak` returns the correct audio bytes.
- [ ] **Test Interface Compliance**:
    - [ ] Create a test that instantiates `DeepgramSTT` and `DeepgramTTS` and asserts `isinstance(provider, STTProvider)` and `isinstance(provider, TTSProvider)` are both `True`.

### Manual Verification
- [ ] Set the `VOICE_PROVIDER` and `DEEPGRAM_API_KEY` environment variables locally.
- [ ] Run the application.
- [ ] Use an API client (e.g., Swagger UI, Postman) to trigger a workflow that uses the new voice services.
- [ ] Verify that the application logs show successful STT/TTS requests being sent to Deepgram.
- [ ] Unset the `DEEPGRAM_API_KEY` and restart the application. Verify that the application fails to start with a clear `ConfigurationError`.

## Definition of Done
### Documentation
- [ ] `CHANGELOG.md` updated with a summary of the new voice abstraction architecture.
- [ ] A new `backend/speech/README.md` is created, explaining the provider model and instructions for adding new providers.
- [ ] All new classes and methods in `interfaces.py`, `factory.py`, and `deepgram.py` have clear docstrings.

### Observability
- [ ] Logs generated by the speech module are structured (JSON) and include a `provider` field.
- [ ] Logs are verified to be free of API keys or other PII.
- [ ] Prometheus metrics for `voice_provider_requests_total` and `voice_provider_request_duration_seconds` are implemented and exposed.

### Testing
- [ ] All new unit tests described in the Verification Plan are implemented and passing.
- [ ] Code coverage for the new `backend/speech/` module meets or exceeds the project's target (e.g., 90%).
- [ ] Integration tests are passed (if applicable to the project structure).