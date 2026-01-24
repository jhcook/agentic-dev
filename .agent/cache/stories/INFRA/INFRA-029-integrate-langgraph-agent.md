# INFRA-029: Integrate LangGraph Conversational Agent

## State

COMMITTED

## Linked Plan

INFRA-027

## Problem Statement

The `VoiceOrchestrator` in INFRA-028 currently uses a placeholder agent that simply echoes user input back as "I heard you say: {text}". To provide real conversational AI capabilities, we need to integrate a production-ready agent framework that can handle:

- Stateful, multi-turn conversations
- Complex reasoning and tool calling
- Streaming responses for low-latency voice interactions
- Conversation checkpointing and resumption

## User Story

As a User, I want to have natural, intelligent conversations with the voice assistant that remembers context, uses tools when needed, and streams responses quickly, so that the interaction feels smooth and human-like.

## Acceptance Criteria

- [ ] **LangGraph Integration**: Replace placeholder agent in `VoiceOrchestrator` with LangGraph agent
- [ ] **Dependencies**: Add `langgraph`, `langchain`, and LLM provider packages to `pyproject.toml`
- [ ] **Agent Configuration**: Create agent with appropriate system prompt and tools
- [ ] **Streaming Responses**: Implement streaming from agent to TTS for low-latency audio output
- [ ] **State Management**: Use LangGraph checkpointer to persist conversation state per `session_id`
- [ ] **Conversation History**: Maintain multi-turn context across WebSocket session
- [ ] **Tool Integration** (optional for MVP): Configure at least one tool (e.g., web search, calculator)
- [ ] **Error Handling**: Gracefully handle agent errors, timeouts, and retries
- [ ] **Testing**: Update `test_voice_flow.py` to include tests with mocked LangGraph agent
- [ ] **Observability**: Add metrics and logs for agent interactions (response time, token usage, tool calls)

## Non-Functional Requirements

- **Latency**: First audio chunk should stream within 1-2 seconds of user finishing speech
- **Memory**: Agent state should not exceed 10MB per session
- **Scalability**: Support concurrent sessions without blocking
- **Reliability**: Agent should handle errors gracefully and not crash WebSocket

## Linked ADRs

- ADR-008
- ADR-011

## Impact Analysis Summary

**Components touched**:

- `.agent/src/backend/voice/orchestrator.py` (major refactor)
- `.agent/pyproject.toml` (add dependencies)
- `.agent/tests/test_voice_flow.py` (update tests)

**Workflows affected**: Voice interaction flow

**Risks identified**:

- LLM API latency could impact response time
- Token costs increase with longer conversations
- Complex agent graphs could be hard to debug

## Test Strategy

### Unit Tests

- Mock LangGraph agent to test orchestrator integration
- Verify conversation state persistence
- Test error handling (LLM timeouts, API errors)

### Integration Tests

- Test with real LangGraph agent (small model like gpt-4o-mini)
- Verify multi-turn conversation flow
- Test streaming response handling
- Verify checkpointing and session resumption

### Manual Tests

- Connect via WebSocket and have multi-turn conversation
- Interrupt and resume conversation
- Test with tool-calling scenarios
- Verify response latency meets requirements

## Rollback Plan

- Revert to placeholder agent
- Remove LangGraph dependencies
- Keep WebSocket infrastructure intact
