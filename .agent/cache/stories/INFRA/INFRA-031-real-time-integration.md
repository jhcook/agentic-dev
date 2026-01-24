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

- [ ] **Streaming Pipeline**: Refactor `VoiceOrchestrator.process_audio` to return an `AsyncGenerator[bytes]` instead of a single `bytes` object.
- [ ] **Agent Fix**: Fix `_invoke_agent` to properly yield text chunks from LangGraph stream (currently exits early).
- [ ] **Sentence Buffer**: Implement `SentenceBuffer` class to aggregate token stream into full sentences (split on `.?!`).
- [ ] **Integration**: Connect pipeline: `Agent Stream -> SentenceBuffer -> TTS -> Audio Stream`.
- [ ] **Router Update**: Update WebSocket endpoint to consume the async generator and send chunks progressively.
- [ ] **Performance**: Verify "Time to First Byte" (TTFB) is minimized while maintaining natural prosody.

## Non-Functional Requirements

- **Latency**: Buffering adds slight latency but improves quality. Must be balanced.
- **Quality**: Prosody must be natural.

## Technical Approach

**Streaming Pipeline Pattern**:

1. **Source**: `_invoke_agent` yields text tokens (Async Generator).
2. **Transform**: `SentenceBuffer` accumulates tokens, yields full sentences.
3. **Synthesis**: `TTSProvider` takes sentences, yields audio bytes.
4. **Sink**: WebSocket router iterates over audio stream, sending bytes to client.

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
