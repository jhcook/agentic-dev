# ADR-033: NotebookLM SQLite Caching

## Status
Accepted

## Context
Previously, NotebookLM synchronization state (like the `notebook_id`) was saved in a plain JSON file (`.agent/cache/notebooklm_state.json`). This pattern caused fragmentation of local state, as we already have a robust local SQLite artifact database (`agent.db`) managed by `agent.db.client`.

## Decision
We will transition the NotebookLM sync state caching to use the core, internal SQLite database via `upsert_artifact` and `get_all_artifacts_content`. A new artifact type `state` (e.g., `id: notebooklm_state`) will be used to store this metadata.

## Consequences
- **Positive:** Centralized state management makes backups, flushes, and database resets (`agent sync flush`) significantly more consistent.
- **Positive:** Reduces proliferation of untracked JSON files in `.agent/cache/`.
- **Negative:** Users lose the ability to manually reset NotebookLM sync state by deleting the JSON file.
- **Mitigation:** We have introduced an `agent sync notebooklm --reset` flag to provide a user-facing command to wipe the state from the SQLite DB.
