# INFRA-098: Unify Console and Voice Agent Interface Layer

## State

COMMITTED

## Problem Statement

Currently, the Agent Console (TUI) and the Voice Agent maintain independent implementations for core logic, including tool registration, prompt pipelines, vector database interactions, and AI service integration. This duplication leads to significant maintenance overhead, inconsistent behavior between channels (drift), and increased risk of bugs when updating shared business logic.

## User Story

As a **Platform Developer**, I want **a unified AgentSession interface layer** so that **I can maintain a single source of truth for agent capabilities and ensure functional parity across TUI and Voice delivery channels.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a new tool or prompt template is registered in the `AgentSession` layer, When either the TUI or Voice Agent is initialized, Then the tool/template is available and behaves identically in both interfaces.
- [ ] **Scenario 2**: The Voice Orchestrator and TUI application must be refactored into "thin adapters" that only handle IO, delegating all state, context, and AI logic to the shared interface.
- [ ] **Negative Test**: System handles AI provider connection failures or malformed tool responses through a centralized error-handling logic that both interfaces inherit gracefully.

## Non-Functional Requirements

- **Performance**: The abstraction layer must introduce < 20ms of overhead to maintain real-time responsiveness for Voice interactions.
- **Security**: Centralized tool execution must enforce consistent permissioning and sandboxing regardless of the entry point.
- **Compliance**: Audit logging for AI interactions and Vector DB queries must be standardized within the shared layer.
- **Observability**: Implement unified OpenTelemetry tracing across the shared session to track request flow from adapter to AI provider.

## Linked ADRs

None yet — this story will likely produce an ADR for the shared AgentSession interface.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-031: Voice Agent Tool Integration

## Impact Analysis Summary

**Components touched:**
- `.agent/src/agent/core/session.py` (New — shared AgentSession interface)
- `.agent/src/agent/tui/app.py` (Refactor — thin adapter over AgentSession)
- `.agent/src/backend/voice/orchestrator.py` (Refactor — thin adapter over AgentSession)
- `.agent/src/agent/core/ai/service.py` (Refactor — unified AI provider abstraction)
- `.agent/src/agent/core/adk/tools.py` (Refactor — shared tool registry)

**Workflows affected:**
- Tool registration and execution.
- Prompt composition and context injection.
- Session state persistence.

**Risks identified:**
- Increased latency in the voice pipeline due to additional abstraction layers.
- Regression in existing TUI-specific tool behaviors during migration.

## Test Strategy

- **Unit Testing**: Validate the `AgentSession` logic in isolation using mocked AI providers.
- **Integration Testing**: Verify that both TUI and Voice adapters can successfully initialize and execute a "Hello World" tool via the shared layer.
- **Parity Testing**: Automated regression suite to ensure output consistency between TUI and Voice for identical prompt inputs.

## Rollback Plan

- Maintain the legacy separate implementations behind a feature flag (`USE_UNIFIED_INTERFACE=false`).
- In the event of critical failure, toggle the flag to revert the adapters to their original direct-implementation logic.

## Copyright

Copyright 2026 Justin Cook
