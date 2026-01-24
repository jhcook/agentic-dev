# WEB-001: Agent Management Console

## State

APPROVED

## Related Story

WEB-001
WEB-002
WEB-003
WEB-004

## Linked ADRs

- ADR-009

## Summary

Develop a comprehensive Web Dashboard ("Agent Console") to unify the fragmented CLI/Config interaction model. This platform will serve as the primary interface for users to interact with, configure, and observe the Agent.

## Objectives

- **Interaction**: Provide a rich, visual Voice/Chat interface (Visualizer, History).
- **Configuration**: Expose `agent.yaml` and `voice.yaml` settings via UI editors.
- **Observability**: Real-time streaming of logs and tool execution traces.
- **Manageability**: Enable/Disable skills and manage sessions.
- **Governance**: Create, Edit, and Track Stories, Plans, and Runbooks.
- **Operations**: Manage Secrets and Sync status.

## Tech Stack Decisions (@Architect/@Web)

- **Frontend**: React + Vite + TailwindCSS.
- **State Management**: **Zustand** or **TanStack Query** (for real-time server state).
- **Audio**: **AudioWorklet** (no main-thread processing).
- **Visuals**: **Canvas API** for waveforms (60fps performance).

## Security Constraints (@Security)

- **Binding**: Admin API must bind strictly to `127.0.0.1` to prevent network exposure.
- **Validation**: Strict schema validation for all config updates.
- **CORS**: Restrictive policy if dev server ports differ.

## Milestones

- **M1: Core Platform (WEB-002)**
  - Initialize React/Vite project in `web/`.
  - Implement Admin API (`routers/admin.py`) for config/system info.
  - Basic Shell (Sidebar, Navigation).
- **M2: Voice Module (WEB-003)**
  - AudioWorklet for 16kHz resampling.
  - WebSocket Client & Visualizer (Canvas).
  - Barge-in handling.
- **M3: Advanced Management (WEB-004)**
  - Config Editor (JSON/YAML Schema form).
  - Prompt Studio (Hot-reload support).
  - Activity Log stream.
- **M4: Governance Desk (WEB-005)**
  - Artifact Browser: View/Edit Stories, Plans, Runbooks.
  - Kanban Board: Drag-and-drop artifacts through states.
  - Preflight Runner: Visual execution of `agent preflight`.
- **M5: Operations Center (WEB-006)**
  - Secrets Manager: UI for `agent secret` (Masked/Unmasked view).
  - Sync Status: Visual artifact synchronization dashboard.
  - Model Registry: `agent list-models` visualizer.

## Risks & Mitigations

- **Risk**: API Security (RCE via Config).
  - **Mitigation**: Bind to localhost only. Admin API disabled by default on non-local envs.
- **Risk**: Frontend/Backend Sync.
  - **Mitigation**: Use strictly typed API interfaces (OpenAPI gen).

## Verification

- **Automated**: E2E Tests (Playwright) for critical paths.
- **Manual**: Usability testing of Voice interaction.
