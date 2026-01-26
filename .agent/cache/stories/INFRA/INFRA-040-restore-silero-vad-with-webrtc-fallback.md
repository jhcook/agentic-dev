# INFRA-040: Restore Silero VAD with WebRTC Fallback

## State

COMMITTED

## Problem Statement

The voice agent currently uses Google WebRTC VAD, which is less accurate and noise-resistant than industry-standard models like Silero VAD. Although Silero was previously implemented, it was reverted due to compatibility issues with `onnxruntime` on Python 3.14. This results in a suboptimal voice interaction experience, particularly in noisy environments.

## User Story

As a Developer, I want the Voice Agent to use high-quality Voice Activity Detection (Silero) where possible, but gracefully fall back to WebRTC VAD if necessary, so that I have the best possible interaction reliability regardless of the environment.

## Acceptance Criteria

- [ ] **Adaptive VAD**: `VADProcessor` in `vad.py` must attempt to initialize Silero VAD (ONNX) on startup.
- [ ] **Robust Fallback**: If `onnxruntime` is missing, Silero initialization fails, or model verification fails, the system must automatically fall back to `webrtcvad`.
- [ ] **Integrity**: The Silero model file must match a hardcoded SHA256 checksum before usage.
- [ ] **Offline Safety**: If the model download fails, the system must gracefully degrade to WebRTC without crashing.
- [ ] **Observability**: The choice of VAD implementation must be clearly logged at startup.
- [ ] **Seamless Integration**: The `VoiceOrchestrator` must remain fully functional regardless of which VAD implementation is active.
- [ ] **Performance**: VAD processing latency must remain below the threshold required for real-time interaction.

## Non-Functional Requirements

- **Performance**: Low-latency VAD is critical for barge-in responsiveness.
- **Security**: Model files should be sourced from verified locations and integrity-checked.
- **Compliance**: Define and document a retention policy for the downloaded model file.
- **Compliance**: Ensure VAD doesn't inadvertently log sensitive audio fragments.

## Linked ADRs

- [ADR-009-offline-local-voice-stack.md](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-009-offline-local-voice-stack.md)
- [ADR-012-hybrid-vad-strategy.md](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-012-hybrid-vad-strategy.md)

## Impact Analysis Summary

Components touched: `backend/voice/vad.py`, `backend/voice/orchestrator.py`
Workflows affected: Voice interaction, specifically interruption and endpointing.
Risks identified: `onnxruntime` overhead on lower-end hardware; potential download failures for the model file.

## Test Strategy

- Unit tests for `VADProcessor` focusing on the initialization and fallback logic.
- Manual verification of "barge-in" reliability with both VAD implementations.

## Rollback Plan

- Revert `vad.py` to the previous WebRTC-only implementation.
