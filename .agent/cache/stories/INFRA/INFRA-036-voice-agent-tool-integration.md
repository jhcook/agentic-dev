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
- [ ] **Persistence**: Replace `MemorySaver` with a persistent checkpointer (e.g., `SqliteSaver` or file-based) so conversations resume after server restart.
- [ ] **Configurable Prompt**: Allow the System Prompt to be updated via `agent config` without code changes.

## Non-Functional Requirements

- **Latency**: Tool usage adds latency. Provide feedback ("Let me check that...") if execution is slow.
- **Safety**: Tools must be sandboxed or explicitly approved.

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
