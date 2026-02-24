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

## Copyright

Copyright 2024-2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
