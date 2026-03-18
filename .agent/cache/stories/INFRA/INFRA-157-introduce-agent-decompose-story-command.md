# INFRA-157: Introduce `agent decompose-story` Command

## State

REVIEW_NEEDED

## Problem Statement

When the AI governance panel determines that a story is too large to implement atomically, it emits a `SPLIT_REQUEST` response and writes a JSON artifact to `.agent/cache/split_requests/<story-id>.json`. Currently there is no CLI command to action that artifact. Developers must manually:

1. Read the JSON `suggestions` array.
2. Create each child story with the correct next available ID (`agent new-story --offline` + manual population).
3. Author a plan file for the parent story ID referencing the children.
4. Update the parent story state to `SUPERSEDED`.

This is error-prone: IDs can clash, child story content is written from memory rather than from the structured suggestions, and the resulting plan file is inconsistently formatted. The process also relies on the developer understanding the ID namespace rules (integers only, no float suffixes).

## User Story

As a **Platform Developer**, I want **`agent decompose-story <STORY-ID>` to automatically process the split-request JSON and generate child stories and a parent plan** so that **I can decompose a story into implementable chunks in a single, governed command without manually managing IDs or file formats.**

## Acceptance Criteria

- [ ] **AC-1 — Discover split request**: `agent decompose-story INFRA-NNN` reads `.agent/cache/split_requests/INFRA-NNN.json` and exits with an error (`code 1`, human-readable message) if the file does not exist.

- [ ] **AC-2 — Assign sequential integer IDs**: The command determines the next N available story IDs (sequential integers in the same namespace, e.g. `INFRA-158`, `INFRA-159`) — one per entry in `suggestions`. IDs are chosen by scanning `.agent/cache/stories/**/*.md` filenames to find the current maximum, then incrementing. No float or alpha suffixes are used.

- [ ] **AC-3 — Create child story files**: For each suggestion string, a new story file is written to `.agent/cache/stories/<PREFIX>/<ID>-<slug>.md` using the standard story template. The `## Problem Statement` and `## User Story` sections are pre-populated from the suggestion text and the parent story's `## Problem Statement`. The `## State` is set to `DRAFT`. The `## Linked ADRs` section carries forward any ADRs from the parent story.

- [ ] **AC-4 — Create parent plan file**: A plan markdown file is written to `.agent/cache/plans/<PREFIX>/<STORY-ID>-plan.md`. The plan title references the parent story title, the `reason` field from the JSON populates a `## Rationale` section, and a `## Child Stories` table lists each new story ID, its slug title, and a `DRAFT` status column.

- [ ] **AC-5 — Update parent story state**: The parent story's `## State` is updated to `SUPERSEDED` using the existing `update_story_state` utility. The SUPERSEDED entry is written with a comment-style annotation: `SUPERSEDED (see plan: <STORY-ID>-plan.md)`.

- [ ] **AC-6 — Idempotency guard**: If child story files already exist for any of the suggested IDs, the command exits with `code 1` and lists the conflicting paths without modifying any files.

- [ ] **AC-7 — Dry-run mode**: `--dry-run` prints a preview of the IDs that would be assigned and the files that would be created/modified, without writing anything to disk.

- [ ] **AC-8 — Sync**: After writing files, the command calls `push_safe` (non-fatal) to sync the new stories and plan to Notion.

- [ ] **Negative Test — Missing JSON**: Given a story ID with no corresponding split-request JSON, the command exits `1` with a clear message: `No split request found for INFRA-NNN. Run 'agent new-runbook INFRA-NNN' to generate one.`

- [ ] **Negative Test — Conflict**: Given that one of the target child story files already exists, no files are written and the command lists all conflicts.

## Non-Functional Requirements

- **Performance**: File scanning to determine next available ID must complete in < 500 ms on a repository with up to 500 story files.
- **Observability**: Structured log events emitted for `decompose_story_start`, `decompose_story_child_created`, `decompose_story_plan_written`, and `decompose_story_complete`.
- **Security**: No PII or story content is logged at INFO level or above.
- **Compliance**: All generated files carry the standard Apache 2.0 copyright header via `apply_license` or inline template expansion.

## Linked ADRs

- ADR-041: Module Decomposition Standards (governs integer-only ID namespace)
- ADR-041: ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-057: JRN-057-impact-analysis-workflow

## Impact Analysis Summary

**Components touched:**
- `agent/commands/decompose_story.py` — **[NEW]** new command module
- `agent/commands/__init__.py` — no changes required; command registers via `agent.main.app` directly
- `agent/commands/utils.py` — **[MODIFIED]** extended `update_story_state` to accept an optional `annotation` suffix, enabling callers to persist state values like `"SUPERSEDED (see plan: ...)"` in a single call
- `agent/core/utils.py` — read-only; `get_next_id`, `sanitize_title`, `get_full_license_header`, `find_story_file`, and `scrub_sensitive_data` reused as-is
- `.agent/templates/story-template.md` — read-only, used as source for child file content
- `.agent/templates/plan-template.md` — read-only, used as source for plan file content (if it exists)
- `.agent/cache/journeys/INFRA/JRN-057-impact-analysis-workflow.yaml` — **[MODIFIED]** implementation files list updated
- `.agent/src/agent/commands/tests/test_decompose_story.py` — **[NEW]** 14 unit and integration tests covering AC-1 through AC-7, `get_next_ids` internals, and `update_story_state` annotation behaviour
- `.agent/src/agent/commands/implement.py` — **[MODIFIED]** out-of-scope bugfix: `yaml.safe_dump` was stripping YAML comment headers (including the Apache 2.0 license) from journey files on every `agent implement` run; fixed by preserving the leading comment block before serialisation
- `.agent/etc/agent.yaml` — **[MODIFIED]** `test_commands` updated to invoke pytest via `.venv/bin/python` instead of system `python3`, ensuring venv-installed dependencies (e.g. `mistune`) are available during `agent preflight`
- `.gitignore` — `.agent/cache/split_requests/` is already gitignored; the command reads local-only JSON artifacts

**Workflows affected:** None changed. `agent new-runbook` continues to write split-request JSON as before; `agent decompose-story` is purely additive.

**Risks identified:**
- ID collision if two developers run `decompose-story` simultaneously on different stories in the same namespace — mitigated by the idempotency guard (AC-6).
- `update_story_state` currently only supports the states in `_VALID_STATES`; `SUPERSEDED` is already in that set.

## Test Strategy

- **Unit — `next_available_ids`**: Given a mocked set of existing story files, assert the correct next N IDs are returned with no gaps or collisions.
- **Unit — `decompose_story` (happy path)**: Mock filesystem; assert child story files and plan file are written with correct content; assert parent state updated to `SUPERSEDED`.
- **Unit — missing JSON**: Assert exit code 1 and expected error message.
- **Unit — conflict guard**: Pre-create one of the target child files; assert no files are written and exit code is 1.
- **Unit — dry-run**: Assert no files are written; assert preview output contains the expected IDs and paths.
- **Integration — end-to-end**: Use an actual `split_requests/INFRA-NNN.json` fixture; assert full file tree is created and parent story state changes.

## Rollback Plan

Remove the `decompose_story.py` module and de-register the command from `cli.py`. Generated child story and plan files can be deleted manually; the parent story state can be reverted to `COMMITTED` using `update_story_state`.

## Copyright

Copyright 2026 Justin Cook
