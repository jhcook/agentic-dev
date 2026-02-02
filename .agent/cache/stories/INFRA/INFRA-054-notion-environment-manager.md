# INFRA-054: Notion Environment Manager - Sync Backends

## State

COMMITTED

## Problem Statement

The current `agent sync` command does not natively support Notion synchronization, leading to the creation of standalone scripts (`pull_from_notion.py`, `sync_to_notion.py`). These scripts need to be integrated into the core CLI to support a unified sync experience where multiple backends for sync can coexist.

## User Story

As a developer, I want the `agent sync` command to support multiple backends (specifically Notion) and allow force overwrites, so that I can manage my environment consistency using a single tool.

## Acceptance Criteria

- [ ] **Port Pull Logic**: The functionality of `pull_from_notion.py` is ported to `agent sync pull`.
- [ ] **Port Push Logic**: The functionality of `sync_to_notion.py` is ported to `agent sync push`.
- [ ] **Multiple Backends**: `agent sync` supports a `--backend` flag (e.g., `--backend=notion`).
- [ ] **Default Behavior**: If no backend is specified, all configured backends are consulted.
- **Self-Healing Sync**:
  - `agent sync` must detect configuration errors (e.g., 404 Not Found for databases).
  - Provide an interactive recovery mechanism (e.g., "Database not found. Run 'agent sync init' to bootstrap?").
  - **New Command**: `agent sync init` to bootstrap backend environments (create databases, schemata).
    - Should support `--backend` flag.
    - Should prompt for missing required configuration (e.g., `NOTION_PARENT_PAGE_ID`).
- [ ] **Force Flag**: `agent sync` supports a `--force` flag to overwrite local or remote state.
- [ ] **Coexistence**: Multiple backends can coexist and be used simultaneously or individually.
- [ ] **Conflict Resolution**:
  - **Interactive Mode**: In case of collisions or discrepancies between backends (or local vs remote), the agent MUST NOT error out. Instead, it should display the conflict and prompt the user to decide which source/destination takes precedence (e.g., "Overwrite Local", "Overwrite Remote", "Skip").
  - `--force` always overrides interactive checks.
- [ ] **Janitor Compatibility**:
  - `agent sync janitor` should respect the `--backend` flag (e.g. `agent sync janitor --backend=notion`).
  - The existing `NotionJanitor` logic remains but is invoked via this standardized interface.

## Related Staged Files

- `.agent/scripts/pull_from_notion.py`
- `.agent/scripts/sync_to_notion.py`

## Linked Plans

- INFRA-048-notion-environment-manager
