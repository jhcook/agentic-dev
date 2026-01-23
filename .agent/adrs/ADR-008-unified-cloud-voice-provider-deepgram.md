# ADR-008: Unified Cloud Voice Provider (Deepgram)

## Status
ACCEPTED

## Context
Our previous/legacy voice stack (ElevenLabs for TTS) or multi-vendor stacks typically incur:
1.  **High Latency:** Multiple hops (asr -> llm -> tts) and non-streaming protocols.
2.  **High Cost:** ElevenLabs is ~10x more expensive than competitors for equivalent speed.
3.  **Complexity:** Managing multiple SDKs and API keys.

## Decision
We will use **Deepgram** as the single unified provider for both Cloud STT (`nova-2`) and Cloud TTS (`aura`).
We will utilize their WebSocket streaming API for both legs of the conversation to minimize latency.

## Consequences
### Positive
- **Speed:** "Time to First Byte" <250ms is achievable via streaming.
- **Cost:** ~92% reduction compared to separate high-end vendors.
- **Simplicity:** One SDK (`deepgram-sdk`), one API key.

### Negative
- **Vendor Lock-in:** Heavy reliance on one provider (mitigated by ADR-007).
- **Voice Variety:** Deepgram Aura has fewer voice options than ElevenLabs.
