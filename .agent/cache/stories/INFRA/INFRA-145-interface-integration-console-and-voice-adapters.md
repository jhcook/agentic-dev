# INFRA-145: Interface Integration Console and Voice Adapters

## State

REVIEW_NEEDED

## Problem Statement

The Console TUI and Voice Orchestrator currently instantiate tools directly from their own implementations. This story refactors both into thin adapters that consume tools exclusively from the centralised `ToolRegistry`.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **Console and Voice to be thin adapters over the ToolRegistry** so that **both interfaces share identical tool behavior and any new tool is automatically available everywhere.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/core/session.py` delegates all tool management to `ToolRegistry` — no direct tool creation.
- [ ] **AC-2**: `agent/tui/session.py` initialises a `ToolRegistry` and passes it to the ADK agent session.
- [ ] **AC-3**: `backend/voice/orchestrator.py` initialises a `ToolRegistry` and uses it instead of scanning for `BaseTool` instances.
- [ ] **AC-4**: `agent/core/engine/executor.py` fixed to yield "Thinking..." to prevent blocking waits.
- [ ] **AC-5**: Both interfaces produce identical tool lists when calling `ToolRegistry.list_tools()`.
- [ ] **Negative Test**: Removing a tool from the registry makes it unavailable in both Console and Voice simultaneously.

## Non-Functional Requirements

- Performance: Registry abstraction adds < 20ms overhead.
- Observability: Unified OpenTelemetry tracing across tool execution.

## Linked ADRs

- ADR-029: ADK Multi-Agent Integration

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Impact Analysis Summary

Components touched: `agent/core/session.py`, `agent/tui/session.py`, `backend/voice/orchestrator.py`, `agent/core/engine/executor.py` (all MODIFY)
Workflows affected: Tool registration, lookup, and execution in both interfaces.
Risks identified: Voice tools use `RunnableConfig` injection — need equivalent context passing in registry.

## Test Strategy

- Integration test: Both adapters initialise and list identical tools.
- Parity test: Same tool invocation produces identical results in Console and Voice.

## Rollback Plan

Feature flag `USE_UNIFIED_REGISTRY=false` reverts adapters to direct implementation.

## Copyright

Copyright 2026 Justin Cook
