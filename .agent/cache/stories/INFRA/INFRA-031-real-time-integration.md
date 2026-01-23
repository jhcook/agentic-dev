# INFRA-031: Real-time Integration

## State
COMMITTED

## Linked Plan
INFRA-030

## Problem Statement
Kokoro works best on full sentences, not individual tokens. To achieve real-time feel, we need to buffer tokens and send chunks at sentence boundaries.

## User Story
As a User, I want the local voice to sound natural and responsive, without long pauses or robotic prosody.

## Acceptance Criteria
- [ ] **Buffering Logic**: Implement a buffer that collects LLM tokens and flushes on punctuation (`.`, `?`, `!`).
- [ ] **Integration**: Connect `LocalTTS` to the Voice Router using this buffering logic.
- [ ] **Performance**: Verify "Real Time Factor" < 1.0 (generation time < playback time).

## Non-Functional Requirements
- **Latency**: Buffering adds slight latency but improves quality. Must be balanced.
- **Quality**: Prosody must be natural.

## Linked ADRs
- ADR-009

## Impact Analysis Summary
Components touched: `backend/routers/voice.py` (or wrapper around TTS)
Workflows affected: Voice Chat
Risks identified: Long sentences causing delay.

## Test Strategy
- Unit test the buffering logic with various token streams.

## Rollback Plan
- Revert buffering logic.
