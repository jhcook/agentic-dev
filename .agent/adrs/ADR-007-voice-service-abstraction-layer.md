# ADR-007: Voice Service Abstraction Layer

## Status
ACCEPTED

## Context
We are implementing a dual-strategy voice architecture:
1.  **Cloud:** Low-latency, high-quality (Deepgram).
2.  **Local:** Privacy-first, offline-capable (Kokoro + Whisper).

Without a proper abstraction layer, the application logic (Voice Router, Frontend) would be tightly coupled to specific SDKs (e.g., `deepgram-sdk`), making it difficult to switch providers or support a hybrid model.

## Decision
We will define strict abstract base classes (Interfaces) for all voice operations.
- **`STTProvider`**: Interface for Speech-to-Text.
- **`TTSProvider`**: Interface for Text-to-Speech.

Consumer code (e.g., the Voice Router) must **only** interact with these interfaces, not concrete implementations. We will use a Dependency Injection pattern to supply the correct implementation (Cloud vs. Local) at runtime based on configuration.

## Consequences
### Positive
- **Flexibility:** Can swap Deepgram for OpenAI, ElevenLabs, or Local Whisper without refactoring core logic.
- **Testability:** Can easily mock the `STTProvider` and `TTSProvider` for unit tests.
- **Hybrid Support:** Can potentially mix and match (e.g., Local STT + Cloud TTS).

### Negative
- **Complexity:** Requires writing wrappers for every provider.
- **Lowest Common Denominator:** Interfaces might limit access to provider-specific features (e.g., Deepgram-specific metadata) unless carefully designed.
