# WEB-004: Advanced Management

## State

COMMITTED

## Problem Statement

Users currently have to manually edit YAML files and restart the agent to change configurations or prompts. This is slow and error-prone.

## User Story

As a User, I want to edit configuration and prompts directly in the Agent Console with validation and hot-reloading, so that I can iterate faster without managing files manually.

## Acceptance Criteria

- [ ] **Unified Dashboard Layout**: Sidebar-based navigation for switching between Voice, Config, and Logs.
- [ ] **Schema-First Config Editor**: UI generated from Pydantic JSON schemas with server-side validation.
- [ ] **Secure Prompt Studio**: Prompt editor with input sanitization and hot-reloading support.
- [ ] **Observability Stream**: Real-time Activity Log via WebSockets showing agent thoughts and tool traces.
- [ ] **Audit Trail**: Logging of configuration changes to the system audit log.

## Governance Consensus

The panel recommends a **technical safety first** approach:

- Use Pydantic v2 to generate JSON schemas for the frontend to ensure UI precisely matches backend expectations.
- Implement strictly validated atomic writes for config files.
- Redact secrets/PII from the Activity Log stream.

## Implementation Strategy

1. **Unified Layout**: Multi-view shell with Sidebar navigation.
2. **Config Engine**: REST API for schema-validated YAML updates.
3. **Prompt Studio**: UI + Hot-reload logic in the Orchestrator.
4. **Activity Log**: Real-time WebSocket stream of agent performance.

## Linked ADRs

- ADR-009 (Agent Console Architecture)
- ADR-006 (Encrypted Secret Management)

## Non-Functional Requirements

- **Performance**: Dashboard should load in < 1s.
- **Reliability**: WebSocket connection should automatically reconnect on failure.
- **Security**: All configuration changes must be audited.
- **Compatibility**: Support for latest Chrome, Firefox, and Safari.

## Impact Analysis Summary

- **Agent Core**: No changes to core reasoning logic.
- **API**: New endpoints for config management and logging.
- **Frontend**: Significant new UI components for the dashboard.
- **Data**: No schema changes to existing database; new audit logs.

## Test Strategy

- **Unit Tests**: Test config validation logic and Pydantic models.
- **Integration Tests**: Verify API endpoints for config updates.
- **E2E Tests**: Test full user flow of editing config and seeing changes.
- **Manual Verification**: Verify UI responsiveness and WebSocket stability.

## Rollback Plan

- Revert changes to `web` directory.
- Restore previous version of backend API handlers.
- No database migration rollback required.
