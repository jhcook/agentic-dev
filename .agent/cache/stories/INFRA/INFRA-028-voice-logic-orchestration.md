# INFRA-028: Voice Logic Orchestration

## State
COMMITTED

## Linked Plan
INFRA-027

## Problem Statement
We need a central "brain" to orchestrate the conversation: listening to audio stream, processing it with an LLM, and generating speech response, all in real-time.

## User Story
As a User, I want to have a natural voice conversation with the assistant, where it listens to me and responds via audio.

## Acceptance Criteria
- [ ] **WebSocket Endpoint**: `/ws/voice` endpoint is created in FastAPI.
- [ ] **Connection Management**: Robust handling of connect/disconnect events, including cleanup of resources (streams) on disconnect.
- [ ] **Orchestration Loop**: `async` logic pipes STT -> LangGraph (LLM) -> TTS without blocking the main thread.
- [ ] **State Management**: Simple session state (e.g., `conversation_id`) is maintained for the duration of the WebSocket connection.
- [ ] **Streaming**: The system streams text/audio as it becomes available (`yield`), not waiting for full completion.
- [ ] **Rate Limiting**: Basic protection against socket flooding (can be simple initially, e.g., 1 connection per user).
- [ ] **Latency**: Initial response audio starts streaming within reasonable time (<1s acceptable for MVP, target <250ms).

## Non-Functional Requirements
- **Concurrency**: Must handle multiple WebSocket connections efficiently.
- **Latency**: Critical for user experience.

## Linked ADRs
- ADR-008

## Impact Analysis Summary
Components touched: `backend/routers/voice.py`
Workflows affected: Voice Chat
Risks identified: Latency accumulation.

## Test Strategy
- Integration test using a WebSocket client ensuring audio bytes are returned.
- **Concurrency Test**: Ensure multiple clients can connect simultaneously without cross-talk or blocking.
- **Error Handling**: Verify system recovers if the LLM or TTS provider timeouts (mocked failure).

## Rollback Plan
- Disable endpoint.
