# INFRA-140: Dynamic Tool Engine and Security

## State

COMMITTED

## Problem Statement

The Voice agent has a dynamic tool creation capability (`backend/voice/tools/create_tool.py`) that is isolated from the Console. This story migrates the AST-based security scanner, path containment, and hot-reload logic into the core `agent/tools/dynamic.py`, making dynamic tool creation available to both interfaces.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **dynamic tool creation with AST security scanning in the core ToolRegistry** so that **both Console and Voice can safely create, import, and hot-reload tools at runtime.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/dynamic.py` implements `create_tool()` with AST-based security scanning (rejecting `eval`, `exec`, `subprocess`, `os.system`, `os.popen`).
- [ ] **AC-2**: Path containment enforces tools are created only within `.agent/src/agent/tools/custom/`.
- [ ] **AC-3**: Hot-reload via `importlib.import_module()` / `importlib.reload()` makes newly created tools immediately available.
- [ ] **AC-4**: `# NOQA: SECURITY_RISK` comment in tool source code bypasses the AST security scan.
- [ ] **AC-5**: `import_tool()` loads a tool from `custom/` into the active `ToolRegistry` session.
- [ ] **Negative Test**: Creating a tool with `eval()` in the source is rejected with a clear `SecurityError`.
- [ ] **Negative Test**: Creating a tool outside `custom/` is rejected with a path traversal error.

## Non-Functional Requirements

- Security: AST scan is the primary security gate — pure stdlib (`os`, `ast`, `importlib`), no framework dependency.
- Compliance: Structured log event emitted for every `create_tool` and `import_tool` invocation.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-031: Voice Agent Tool Integration

## Impact Analysis Summary

Components touched: `.agent/src/agent/tools/dynamic.py` (NEW), `.agent/src/agent/tools/custom/` (NEW directory)
Workflows affected: Dynamic tool creation and hot-reload lifecycle.
Risks identified: Migration is pure stdlib — no LangChain dependency in core logic.

## Test Strategy

- Unit tests for `_security_scan()` with forbidden patterns.
- Unit tests for path containment enforcement.
- Integration test: create → import → execute a dynamic tool.

## Rollback Plan

Delete `dynamic.py` and `custom/` — no existing code depends on them yet.

## Copyright

Copyright 2026 Justin Cook
