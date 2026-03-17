# INFRA-139: Core Tool Registry and Foundation

## State

COMMITTED

## Problem Statement

INFRA-098 requires a centralised `ToolRegistry` to replace fragmented tool implementations across Console and Voice. This story establishes the foundational `agent/tools/` package and the `ToolRegistry` class that all subsequent stories build upon.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **a `ToolRegistry` class with standard `Tool` and `ToolResult` data classes** so that **all tools across Console and Voice can be registered, looked up, and executed through a single interface.**

## Acceptance Criteria

- [ ] **AC-1**: `.agent/src/agent/tools/__init__.py` exports `ToolRegistry` with `register()`, `get_tool()`, `list_tools()`, and `unrestrict_tool()` methods.
- [ ] **AC-2**: `Tool` and `ToolResult` Pydantic models define the standard tool interface (name, description, parameters schema, handler callable).
- [ ] **AC-3**: The registry supports categorising tools by domain (e.g., `filesystem`, `shell`, `search`).
- [ ] **Negative Test**: Registering a tool with a duplicate name raises `ToolRegistryError`.

## Non-Functional Requirements

- Performance: Registry lookup must be O(1) via dict-based storage.
- Security: `unrestrict_tool()` must log an audit event when called.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Impact Analysis Summary

Components touched: `.agent/src/agent/tools/__init__.py` (NEW), `.agent/src/agent/tools/tests/__init__.py` (NEW), `.agent/src/agent/tools/tests/test_registry.py` (NEW), `.agent/cache/journeys/INFRA/JRN-023-voice-logic-orchestration.yaml` (MODIFIED)
Workflows affected: Tool registration and lookup.
Risks identified: None — greenfield module.

## Test Strategy

- Unit tests for register/get/list/unrestrict methods.
- Test duplicate name rejection.
- Test tool categorisation filtering.

## Rollback Plan

Delete the `agent/tools/` package — no existing code depends on it yet.

## Copyright

Copyright 2026 Justin Cook
