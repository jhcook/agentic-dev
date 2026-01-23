# INFRA-030: Local Voice Integration (Kokoro + Whisper)

## State
APPROVED

## Related Story
INFRA-030
INFRA-031

## Linked ADRs
- ADR-007
- ADR-009

## Summary
Implement a fully offline, privacy-first voice stack. Ideal for local testing or "air-gapped" deployments. This complements the Cloud Voice Integration by providing a free, local alternative.
See [ADR-007](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-007-voice-service-abstraction-layer.md) for abstraction details and [ADR-009](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-009-offline-local-voice-stack.md) for local stack selection.

## Objectives
- **Privacy First:** Ensure all voice processing (STT/TTS) happens locally on-device.
- **Zero Cost:** Eliminate cloud API costs for development and local usage.
- **Latency Control:** Achieve near real-time performance using streaming "tricks" (sentence buffering).

## Milestones
- **M1:** Local Setup
  - Download and configure `kokoro-v0_19.onnx` and models.
  - Install dependencies (`kokoro-onnx`, `soundfile`).
  - Create `LocalSTT` (Faster-Whisper) and `LocalTTS` (Kokoro) implementations of the core interfaces.
- **M2:** Real-time Integration
  - Implement sentence-boundary buffering for Kokoro to optimize prosody vs latency.
  - Verify "Real Time Factor" < 1.0 on standard hardware (M1/M2 or GPU).

## Risks & Mitigations
- **Risk:** High latency on non-GPU hardware.
  - **Mitigation:** Fallback to cloud provider if local inference is too slow, or use quantized models.
- **Risk:** Prosody degradation with short text chunks.
  - **Mitigation:** Buffer 2-3 tokens past punctuation or use smart sentence splitting.

## Verification
- **Automated:**
  - Unit tests for buffering logic.
- **Manual:**
  - Performance test: Measure generation time vs playback time on M1 Air.
  - Privacy check: Disconnect internet and verify voice loop still works.
