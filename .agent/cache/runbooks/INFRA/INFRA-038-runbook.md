# Governance Council Tool Suite

## Status

OPEN

## Context & Objectives

The Voice Agent currently lacks specific tools to perform the duties of the Governance Council roles. It effectively has no "hands" to manipulate the codebase or verify compliance, forcing it to hallucinate responses or fail.
This Runbook defines the implementation of a **Modular Tool Suite** mapping to the 10 Governance Roles (Architect, QA, Security, etc.), enabling the agent to act as a true proxy for the council.

### Panel Review Findings

### @Architect (System Design)

- **Verdict**: APPROVE
- **Feedback**:
  - The modular split (`backend.voice.tools.*`) is clean and extensible.
  - **Optimization**: For MVP, sync file scanning is acceptable, but consider caching for `list_adrs` in future.
  - **Constraint**: Ensure `tools.py` stays purely as a registry/facade if needed, but per plan we are refactoring it into a package.

### @Security (Safety)

- **Verdict**: APPROVE WITH CAUTION
- **Feedback**:
  - **Input Sanitization**: `subprocess.run` usage in `git.py` and `qa.py` must use list arguments (not shell=True) to prevent injection.
  - **Secrets**: The `scan_secrets` tool MUST NOT log found secrets to the conversation or logs, only reference line numbers.

### @QA (Testing)

- **Verdict**: APPROVE
- **Feedback**:
  - **Testing**: Unit tests for the tools themselves are critical.
  - **Output Management**: Truncate large outputs from logs/diffs to prevent context window overflow.

### @Product (Value)

- **Verdict**: APPROVE
- This feature is the core enable for "Agentic Development". High value.

### Implementation Plan

#### Phase 1: Package Structure (Complete)

- [x] Create `backend/voice/tools/`
- [x] Move `git.py` to package.

### Phase 2: Role Module Implementation

- [ ] **Architect Tools** (`architect.py`):
  - `list_adrs()`: Scan `.agent/rules` and `docs/architecture`.
  - `read_adr()`: Read file content.
  - `search_rules()`: Grep rules folder.
- [ ] **QA Tools** (`qa.py`):
  - `run_backend_tests(path)`: Execute `pytest`.
  - `run_frontend_lint()`: Execute `npm run lint`.
  - `get_coverage()`: Read `coverage.xml` or similar.
- [ ] **Security Tools** (`security.py`):
  - `scan_secrets(content)`: Regex scan for keys.
- [ ] **Observability Tools** (`observability.py`):
  - `get_recent_logs(n)`: Tail `agent.log`.
- [ ] **Core/Project Tools** (`project.py`, `core.py`):
  - `read_story`, `list_runbooks`.
  - `read_file`, `list_files`.

### Phase 3: Meta Tools (Self-Evolution)

- [ ] **Meta Module** (`meta.py`):
  - `draft_new_tool(name, code)`: Write python file to `backend/voice/tools/custom/`.
  - `list_capabilities()`: Inspect available tools.
- [ ] **Dynamic Registry** (`registry.py`):
  - Implement `get_all_tools()` that aggregates Standard + Custom tools.
  - Ensure safe reloading.

### Phase 4: Integration

- [ ] Update `orchestrator.py` to import from `registry.py`.
- [ ] Update `voice_system_prompt.txt` to train agent on new tools.

### Verification Plan

#### Automated

- **Unit Tests**: Create `tests/test_voice_tools.py` to verify each tool function via mock.

### Manual Voice Verification

1. **Architect**: "List all architecture rules." -> Should return list from `.agent/rules`.
2. **QA**: "Run the backend tests." -> Should trigger pytest.
3. **Self-Evolution**: "Learn how to checking config files." -> Should call `draft_new_tool`.

### Rollback Plan

- Revert `orchestrator.py` to use old `tools.py`.
- Delete `backend/voice/tools/` package.
