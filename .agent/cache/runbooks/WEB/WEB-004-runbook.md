# WEB-004: Advanced Management

## State

ACCEPTED

## Goal

Implement "Advanced Management" for the Agent Console, moving static YAML/Prompt management into a dynamic, schema-driven UI with real-time observability.

## Panel Review Findings

### @Architect

**Sentiment**: Positive
**Advice**:

- Use a strictly decoupled "Management API" in `backend/main.py`.
- Implement a `ConfigProvider` singleton in the backend that handles file I/O safely via atomic writes (`os.replace`).
- Use `pydantic.BaseModel.model_json_schema()` to drive the frontend forms.

### @Security

**Sentiment**: Positive
**Advice**:

- Use `env -u VIRTUAL_ENV uv run agent secret` integration for any sensitive fields in the config editor; never save raw secrets to `agent.yaml`.
- Sanitize prompt inputs in the React UI (check for illegal characters or forbidden tokens).
- Ensure WebSocket logs are redacted before transit.

### @Web

**Sentiment**: Positive
**Advice**:

- Implement a Sidebar layout using Tailwind CSS.
- Use `zustand` for managing the application view state (current tab, connection status).
- For the log view, use a specialized "Terminal" look with auto-scroll.

### @QA

**Sentiment**: Neutral
**Advice**:

- Unit tests required for the `ConfigUpdater` logic (mocking file I/O).
- E2E tests using `playwright` to verify "Save & Hot Reload" loop.

### @Product

**Sentiment**: Positive
**Advice**:

- Ensure the "Activity Log" is scannable; differentiate between "Thinking" and "Action" (tool calls).
- Add a "Revert" or "Undo" button for configuration changes.

## Implementation Steps

### Phase 1: Unified Dashboard Layout

1. **[NEW] [Layout.tsx](file:///.agent/web/src/components/Layout.tsx)**: Create a global layout component with a sidebar.
2. **[MODIFY] [App.tsx](file:///.agent/web/src/App.tsx)**: Update to use a view-switcher (State-based or Router).
3. **[NEW] [Navigation.tsx](file:///.agent/web/src/components/Navigation.tsx)**: Sidebar navigation with icons (Voice, Config, Logs).

### Phase 2: Configuration & Prompt Studio

1. **[MODIFY] [main.py](file:///.agent/src/backend/main.py)**: Add `/admin/config` and `/admin/prompts` GET/POST endpoints.
2. **[NEW] [config_updater.py](file:///.agent/src/backend/admin/config_updater.py)**: Helper for atomic YAML writes and schema generation.
3. **[NEW] [ConfigEditor.tsx](file:///.agent/web/src/components/ConfigEditor.tsx)**: Dynamic form generator using fetched JSON schema.
4. **[NEW] [PromptStudio.tsx](file:///.agent/web/src/components/PromptStudio.tsx)**: Specialized editor for system personas.

### Phase 3: Activity Log & Observability

1. **[MODIFY] [orchestrator.py](file:///.agent/src/backend/voice/orchestrator.py)**: Hook into the agent's stream to broadcast "thoughts" via a messaging bus.
2. **[MODIFY] [main.py](file:///.agent/src/backend/main.py)**: Implement `/ws/logs` to stream agent activity.
3. **[NEW] [ActivityLog.tsx](file:///.agent/web/src/components/ActivityLog.tsx)**: Terminal-style log viewer in the frontend.

## Verification Plan

### Automated Tests

- **Backend**: `pytest .agent/tests/admin/test_config.py` (Validate schema generation and atomic writes).
- **E2E**: `playwright test` (Verify that updating a prompt in Config view updates the agent's persona in Voice view).

### Manual Verification

1. Open Console → Configuration.
2. Change `agent_name`.
3. Save and verify it appears in Voice Client status immediately.
4. Check `.agent/etc/agent.yaml` to confirm atomic write successful.
