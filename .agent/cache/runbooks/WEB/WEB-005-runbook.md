# WEB-005: Governance Desk

## State

ACCEPTED

## Goal

Develop a "Governance Desk" in the Agent Console to visualize and manage the governance estate (Stories, Plans, Runbooks, ADRs) via a filesystem-backed UI, ensuring architectural consistency and ease of use.

## Panel Review Findings

### @Architect

**Sentiment**: Positive
**Advice**:

- **Single Source of Truth**: The desk must read/write directly to `.agent/cache/` markdown files. Do not cache state in a database.
- **Dependency Graph**: Implement a Python-based parser in the backend to regex-scan files for `[ID]` links to build the "Estate Graph".
- **State Enforcement**: The `ConfigUpdater` logic should be reused for atomic writes to ensure data integrity.

### @Security

**Sentiment**: Neutral
**Advice**:

- **Input Sanitization**: Ensure the Markdown editor does not allow XSS. Use a safe renderer.
- **Path Traversal Prevention**: The backend API (`routers/governance.py`) must strictly validate file paths to ensure they stay within `.agent/cache/`.
- **Audit Logging**: All artifact modifications must be logged to the `admin/logger.py` bus.

### @Web

**Sentiment**: Positive
**Advice**:

- **Libraries**: Use `React Flow` for the Estate Graph, `@dnd-kit/core` for Kanban, and `MDXEditor` (or lightweight alternative) for artifact editing.
- **Performance**: The Estate Graph might get large; use virtualization or simplified nodes if performance drops.
- **WebSocket**: Reuse the existing `/ws/admin/logs` or create `/ws/admin/governance` for streaming `preflight` output.

### @QA

**Sentiment**: Neutral
**Advice**:

- **Unit Tests**: Test the graph parsing logic extensively with mock markdown files.
- **E2E**: Verify the "Drag-to-Commit" flow. Ensure that visual state updates immediately and resists refresh.

## Implementation Steps

### Phase 1: Backend Infrastructure

1. **[NEW] [routers/governance.py](file:///.agent/src/backend/routers/governance.py)**:
    - `GET /api/admin/governance/artifacts`: List all stories/plans/runbooks/ADRs.
    - `GET /api/admin/governance/graph`: Return nodes/edges for the Estate Graph.
    - `POST /api/admin/governance/artifact`: Atomic write for an artifact.
    - `POST /api/admin/governance/preflight`: Trigger preflight shell command.
2. **[MODIFY] [main.py](file:///.agent/src/backend/main.py)**: Register the new router.

### Phase 2: Governance Desk UI (Shell & Kanban)

1. **[NEW] [GovernanceDesk.tsx](file:///.agent/web/src/components/GovernanceDesk.tsx)**: Main layout container.
2. **[NEW] [KanbanBoard.tsx](file:///.agent/web/src/components/governance/KanbanBoard.tsx)**: `@dnd-kit` implementation for Stories.
3. **[MODIFY] [Navigation.tsx](file:///.agent/web/src/components/Navigation.tsx)**: Add "Desk" link.

### Phase 3: Estate Graph & Editor

1. **[NEW] [EstateGraph.tsx](file:///.agent/web/src/components/governance/EstateGraph.tsx)**: `React Flow` visualization.
2. **[NEW] [ArtifactEditor.tsx](file:///.agent/web/src/components/governance/ArtifactEditor.tsx)**: Markdown editor with save functionality.

## Verification Plan

### Automated Tests

- **Backend**: `pytest .agent/tests/admin/test_governance.py` (Verify graph parsing and path validation).
- **E2E**: `playwright test` (Test creating a story, dragging it to "Planned", and verifying the file updates on disk).

### Manual Verification

1. Create a new Story in the UI.
2. Go to terminal: `cat .agent/cache/stories/WEB/STORY-XXX.md`. Verify content matches.
3. Drag story to "COMMITTED".
4. Run Preflight from UI. Verify output streams to the console window.
