# INFRA-036: Voice Agent Tool Integration

## State

COMMITTED

## Problem Statement

The current `VoiceOrchestrator` uses a basic conversational agent without access to tools or persistent memory. This limits its utility to general chat. Users need the voice assistant to perform actions (e.g., look up documentation, check status) and remember context across restarts.

## User Story

As a Developer, I want the Voice Agent to be able to use tools and remember our conversation history persistently, so that I can have meaningful, multi-turn interactions that result in real actions.

## Acceptance Criteria

- [ ] **Tool support**: Configure `VoiceOrchestrator` to accept a list of tools (e.g., `LangGraph` tools).
- [ ] **Example Tool**: Implement a basic tool (e.g., `lookup_documentation`) and wire it up.
- [ ] **Persistence**: Replace `MemorySaver` with `SqliteSaver` (stored in `.agent/storage/`) for durable context.
- [ ] **Configurable Prompt**: Allow the System Prompt to be updated via `env -u VIRTUAL_ENV uv run agent config`.
- [ ] **Transcript Sync**: Emit JSON events (User Text, Agent Text, Tool Result) over WebSocket to enable frontend chat history.
- [ ] **Latency Handling**: If tool execution > 1s, play "Thinking..." filler audio/sound.
- [ ] **Safety**: Sensitive tools must require verbal confirmation ("Are you sure?").
- [ ] **Observability**: Trace tool execution duration and arguments via OpenTelemetry/LogBus.

## Non-Functional Requirements

- **Latency**: Tool usage behavior must not degrade perceived voice responsiveness (use fillers).
- **Safety**: Tools must be sandboxed. No unchecked filesystem access outside `.agent/`.
- **Architecture**: Tool definitions must be decoupled from the Orchestrator.

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `backend/voice/orchestrator.py`
Workflows affected: Voice Chat
Risks identified: Long tool execution times causing timeouts.

## Test Strategy

- Unit test tools independently.
- Integration test: Mock tool execution and verify agent uses tool output in response.

## Rollback Plan

- Revert configuration changes.
