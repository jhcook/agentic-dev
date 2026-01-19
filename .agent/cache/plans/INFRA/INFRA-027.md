# INFRA-027: Cloud Voice Integration (Unified Deepgram)

## State
APPROVED

## Related Story
INFRA-027
INFRA-028
INFRA-029

## Summary
Implement a real-time voice interface using a single provider (Deepgram) for both Speech-to-Text (STT) and Text-to-Speech (TTS). This architectural shift aims to dramatically reduce cost and latency by replacing multi-vendor stacks (e.g., ElevenLabs) with a unified, streaming-first approach.

## Objectives
- **Minimize Latency:** Achieve "Time to First Byte" of <250ms for voice responses.
- **Reduce Cost:** Lower voice synthesis costs by ~92% (from ~$18.00 to ~$1.50 per 100 minutes).
- **Future-Proof Architecture:** Design with strict interfaces and dependency injection to support swapping providers (e.g., local Whisper/TTS) in the future without refactoring core logic.

## Milestones
- **M1:** Backend Core & Abstractions
  - Define `speech.interfaces.STTProvider` and `speech.interfaces.TTSProvider` abstract base classes.
  - Implement Dependency Injection container (or pattern) for voice services.
  - Create `DeepgramSTT` and `DeepgramTTS` implementations.
  - Create `voice.py` router injecting these providers.
- **M2:** Voice Logic Implementation
  - Implement "Listen" (STT stream).
  - Implement "Think" (LLM via LangGraph, generating conversational text).
  - Implement "Speak" (TTS stream via Deepgram Aura).
- **M3:** Frontend Audio Integration
  - Update React Native audio player to handle streaming MP3/Linear16 chunks.
- **M4:** Verification & Tuning
  - Latency testing and cost verification.

## Risks & Mitigations
- **Risk:** Latency exceeds 250ms due to LLM token generation slowness.
  - **Mitigation:** Ensure LangGraph is streaming tokens immediately and TTS pipeline accepts small text chunks.
- **Risk:** Audio packet loss or jitter over WebSocket.
  - **Mitigation:** Implement client-side buffering and robust reconnection logic.
- **Risk:** Deepgram Aura voice quality vs ElevenLabs.
  - **Mitigation:** Tune LLM prompt for shorter, more natural sentences which Aura handles best.

## Verification
- **Automated:**
  - Unit tests for `voice.py` router logic (mocked WebSocket).
- **Manual:**
  - "Hello World" voice test: Speak to app, verify instantaneous audio response.
  - Dashboard Check: Confirm usage in Deepgram console reflects "Nova-2" and "Aura" models.
  - Latency Measurement: Log timestamps from "EndOfSpeech" to "FirstAudioByte".
