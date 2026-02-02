# INFRA-054: Notion Environment Manager - Sync Backends

## State

ACCEPTED

## Goal Description

Integrate Notion synchronization into the core `agent sync` command, allowing users to synchronize their environments with Notion databases using a unified CLI experience. The integration should support a `--backend` flag to specify Notion as the backend, a `--force` flag to overwrite local or remote state, and coexistence with other backends. Additionally, the `agent sync janitor` command should also support the `--backend` flag for Notion.

## Panel Review Findings

**@Architect:**
The proposed solution addresses the user story effectively by integrating Notion synchronization into the `agent sync` command. The use of a `--backend` flag allows for easy selection of different backends, and the `--force` flag provides a way to handle conflicts. The coexistence of multiple backends is also a good design choice. However, the interaction between different backends and potential conflicts between them needs to be carefully considered during implementation. Specifically, the conflict resolution mechanism should be robust and provide clear guidance to the user. Also, we need an ADR for how we represent the agent config in Notion.

**@Security:**
The implementation needs to ensure that Notion API keys are securely stored and accessed. The `--force` flag should be used with caution, as it could potentially overwrite sensitive data. Input validation and sanitization should be implemented to prevent injection attacks. Audit logging should be implemented to track synchronization events.

**@QA:**
Thorough testing is required to ensure that the Notion synchronization works as expected. Unit tests should be written to test the individual components, and integration tests should be written to test the interaction between the components. Manual testing should be performed to verify the functionality and usability of the command. Edge cases and error conditions should be tested to ensure that the application handles them gracefully. We must perform end-to-end tests with various Notion schemas.

**@Docs:**
The documentation needs to be updated to reflect the new functionality. The `agent sync` command documentation should be updated to include the `--backend` and `--force` flags. Examples should be provided to show how to use the command with Notion. The documentation should also include information on how to configure the Notion backend.

**@Compliance:**
The implementation needs to comply with all applicable data privacy regulations. Notion API keys should be stored securely. User consent should be obtained before synchronizing data with Notion. Data retention policies should be implemented to ensure that data is not stored for longer than necessary.

**@Observability:**
Metrics should be added to track the number of synchronization events, the amount of data synchronized, and the time taken to synchronize. Logs should be structured and free of PII. Alerts should be configured to notify administrators of any errors or issues. We also need to track which backends are being used.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert prints to logger in `src/notion_sync.py` (after porting from script).
- [ ] Fix formatting in `src/agent/cli.py` around sync command (after modifications).

## Implementation Steps

### 1. Port Notion Logic

#### NEW `.agent/src/agent/sync/notion.py`

- Create a new module to house the logic ported from `.agent/scripts/pull_from_notion.py` and `.agent/scripts/sync_to_notion.py`.
- Implement `NotionPuller` and `NotionSyncer` classes (or functions) adapted for the core library.
- **Refactor**: Ensure they utilize the common `agent.core.notion.client`.
- **Conflict Logic**: Implement `check_conflict(local, remote)` returning a Diff or Boolean.

### 2. Update CLI Interface

#### MODIFY `.agent/src/agent/sync/cli.py`

- Update `pull`, `push`, and `janitor` commands to accept:
  - `backend: str = typer.Option(None, "--backend", help="Specific backend to use (e.g. notion)")`
  - `force: bool = typer.Option(False, "--force", help="Force overwrite without prompting")`
- Pass these arguments to the underlying sync implementation.

### 3. Orchestrate Backends

#### MODIFY `.agent/src/agent/sync/sync.py`

- Introduce a "Backend Orchestrator" pattern.
- In `pull()` and `push()`:
  - Check the `backend` argument.
  - If `notion` (or None/All): Invoke `agent.sync.notion` logic.
  - Maintain existing Supabase/Local sync logic (if it exists) as the "Default" or clearly separated backend.
- **Implement Interactive Conflict Resolution**:
  - When a conflict is detected (e.g. Notion has newer content than Local):
    - If `--force` is True: Overwrite.
    - Else: Use `rich.prompt` or `typer.confirm` to ask:
            > "Conflict detected for [ID]. Remote is changed. Overwrite Local? [y/N/s(skip)]"

### 4. Janitor Integration

#### MODIFY `.agent/src/agent/sync/cli.py` & `.agent/src/agent/sync/janitor.py`

- Ensure `janitor` command respects `--backend`.
- If `backend="notion"` (default), run `NotionJanitor`.

### Phase 3: Self-Healing & Bootstrapping

- [ ] **Refactor Schema Manager**:
  - Move logic from `.agent/scripts/notion_schema_manager.py` to `src/agent/sync/bootstrap.py`.
  - Refactor to use `agent.core.notion.client` instead of `urllib`.
  - Implement `Bootstrap` class with `run()` method accepting `backend` argument.

- [ ] **Implement `agent sync init`**:
  - Update `src/agent/sync/cli.py` to add `init` command.
  - Wire to `agent.sync.sync.init(backend=...)`.

- [ ] **Interactive Error Handling**:
  - Update `src/agent/sync/notion.py` to catch 404 errors.
  - In `catch` block, check if error is "object_not_found".
  - If yes, use `rich.prompt.Confirm` to ask user if they want to run `agent sync init`.

### 5. Cleanup

#### DELETE `.agent/scripts/pull_from_notion.py`

#### DELETE `.agent/scripts/sync_to_notion.py`

## Verification Plan

### Automated Tests

- [ ] **Unit**: Test `notion.py` logic (parsing, diffing) without actual API calls (Mock).
- [ ] **Unit**: Test interactive prompt logic (mocking user input).

### Manual Verification

- [ ] **Pull Test**: `agent sync pull --backend=notion`. Verify local files update.
- [ ] **Push Test**: `agent sync push --backend=notion`. Verify Notion updates.
- [ ] **Conflict Test**: Modify both Local and Notion. Run sync. Verify Interactive Prompt appears.
- [ ] **Force Test**: Run sync with `--force` on conflict. Verify no prompt and overwrite happens.
- [ ] **Janitor Test**: `agent sync janitor --backend=notion`. Verify it runs.

## Definition of Done

- Runbook is ACCEPTED.
- Code is merged.
- Scripts are deleted.
