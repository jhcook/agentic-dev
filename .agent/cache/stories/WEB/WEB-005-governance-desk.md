# WEB-005: Governance Desk

## State

COMMITTED

## Problem Statement

Governance workflows (`story`, `plan`, `runbook`, `preflight`) are currently CLI-only, which makes it hard to visualize the state of work, track progress, or easily edit artifacts without context switching.

## User Story

As a User, I want a visual Governance Desk to manage Stories, Plans, Runbooks, and ADRs, visualizing their relationships and impact, so that I can maintain a coherent and documented architectural estate.

## Acceptance Criteria

- [ ] **Artifact Browser**: Tree/List view of all Stories, Plans, Runbooks, and ADRs (Source: Filesystem).
- [ ] **ADR Manager**: Interface to create, edit, and prohibit/deprecate Architectural Decision Records (Sanitized input).
- [ ] **Estate Graph**: Visual graph using `React Flow` showing links between Stories, Plans, and ADRs.
- [ ] **Artifact Editor**: Markdown editor (`MDXEditor` or similar) with preview for editing artifacts.
- [ ] **Kanban Board**: Drag-and-drop interface (`dnd-kit`) to move Stories between states, enforcing ADR-004 transitions.
- [ ] **Visual Preflight**: UI to run `env -u VIRTUAL_ENV uv run agent preflight` and stream results via WebSocket.

## Governance Consensus

The panel recommends a **filesystem-first** approach with strict state enforcement:

- **Architect**: The filesystem is the single source of truth. No separate database.
- **Security**: Strict input sanitization for filesystem writes. Full audit logging of actions.
- **Frontend**: Use `React Flow` for graphs and `@dnd-kit` for Kanban.
- **Backend**: Implement a robust markdown-to-graph parser (`[ID]` link detection).

## Linked ADRs

- ADR-004 (Governance State Enforcement)
- ADR-005 (AI-Driven Governance Preflight)
- ADR-010 (Model Context Protocol Adoption)

## Non-Functional Requirements

- **Responsiveness**: Drag-and-drop operations must be instant (< 100ms visual feedback).
- **Consistency**: UI state must always reflect the underlying filesystem/cache state.
- **Fail-Safe**: If preflight fails, the system must clearly highlight blocking headers.
- **Security**: All artifact edits must be sanitized to prevent XSS/Injection.
- **Auditability**: All state changes must be logged to the system audit stream.

## Impact Analysis Summary

- **Agent Core**: No changes.
- **Backend**: New API endpoints to list artifacts and trigger git operations.
- **Frontend**: New "Desk" view with Kanban board and Markdown editor.

## Test Strategy

- **Unit Tests**: Test markdown parsing and state transition logic.
- **E2E Tests**: Test the full flow of dragging a story to "COMMITTED" and generating a runbook.
- **Manual Verification**: Verify drag-and-drop mechanics on different screen sizes.

## Rollback Plan

- Revert frontend changes (feature flagged if possible).
- Backend API endpoints are additive, so low risk.
