# INFRA-044: Restore Agent Sync Functionality

## State

COMMITTED

## Problem Statement

The `env -u VIRTUAL_ENV uv run agent sync` command and its subcommands (`pull`, `push`, `scan`, `status`) are currently broken. The CLI entry point in `src/agent/main.py` incorrectly points to a broken/incomplete `src/agent/sync/main.py` module instead of the correct `src/agent/sync/cli.py`. This prevents users from syncing artifacts between the local cache and the remote database.

## User Story

As a developer, I want to use `env -u VIRTUAL_ENV uv run agent sync pull`, `push`, and `status` so that I can synchronize my local artifacts with the team's shared state and ensure my local cache is up to date. I want these commands to be secure (requiring authentication) and provide clear feedback.

## Acceptance Criteria

- [ ] **Scenario 1**: `env -u VIRTUAL_ENV uv run agent sync --help` displays the correct subcommands (pull, push, status, scan, delete).
- [ ] **Scenario 2**: `env -u VIRTUAL_ENV uv run agent sync status` runs available and clearly indicates if local is "ahead", "behind", or "synced" with remote.
- [ ] **Scenario 3**: `env -u VIRTUAL_ENV uv run agent sync pull` and `push` **require authentication**.
  - Must use the `with_creds` decorator (refactored to a shared module).
  - Fails gracefully with a clear error if not authenticated.
- [ ] **Scenario 4**: `env -u VIRTUAL_ENV uv run agent sync` wiring relies on `app.add_typer` in `main.py` pointing to `agent.sync.cli:app`.
- [ ] **Scenario 5**: The broken file `src/agent/sync/main.py` is removed.

## Non-Functional Requirements

- **Security**: All sync operations interacting with remote (push/pull) MUST be authenticated.
- **Architecture**: `with_creds` decorator must be moved from `main.py` to `agent.core.decorators` (or similar) to allow reuse in `agent.sync.cli` without circular imports.
- **UX**: Status command must be human-readable.
- Maintain existing CLI structure matching `typer` conventions.

## Linked ADRs

- ADR-017: Agent CLI Command Governance

## Impact Analysis Summary

Components touched: `.agent/src/agent/main.py`, `.agent/src/agent/sync/cli.py`, `.agent/src/agent/core/decorators.py` (New), `.agent/src/agent/sync/main.py` (Delete)
Workflows affected: Development workflow (syncing artifacts)
Risks identified: Circular imports if decorator not moved carefully.

## Test Strategy

- **Manual Verification**:
  - `env -u VIRTUAL_ENV uv run agent sync --help` (Smoke Test)
  - `env -u VIRTUAL_ENV uv run agent sync status` (UX Check)
  - `env -u VIRTUAL_ENV uv run agent sync pull` (Auth Check - try without creds)
- **Automated**:
  - New Smoke Test Script: `tests/smoke_sync.sh` that checks `env -u VIRTUAL_ENV uv run agent sync --help` exit code.

## Rollback Plan

To rollback this change, the following steps must be taken:

1.  Revert the changes made to `src/agent/main.py` to point back to the original (potentially non-functional) state. This involves reverting the commit that changed the CLI entrypoint.
2.  Revert or delete the new `src/agent/core/decorators.py` file. 
3.  Revert the changes made in `src/agent/sync/cli.py` related to authentication and integration with the `with_creds` decorator (if any were necessary).
4.  If `src/agent/sync/main.py` was deleted, restore it from version control. Although it's broken, restoring it will ensure the system is in its exact previous state.
5.  Verify that the `env -u VIRTUAL_ENV uv run agent sync` command is no longer functional, indicating a successful rollback to the previous, broken state.
