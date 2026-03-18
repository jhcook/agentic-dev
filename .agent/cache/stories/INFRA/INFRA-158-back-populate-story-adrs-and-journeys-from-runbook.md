# INFRA-158: Back-Populate Story with ADRs and Journeys Identified During Runbook Generation

## State

COMMITTED

## Problem Statement

When `agent new-runbook` generates a runbook, the AI Governance Panel often identifies relevant Architectural Decision Records (ADRs) and User Journeys that the implementation must respect or extend. These references appear in the runbook under `## Linked Journeys` and `## Panel Review Findings` — but they are never written back to the parent story. The story's `## Linked ADRs` and `## Linked Journeys` sections remain empty (or contain `None`) even though the runbook has populated those fields with concrete references.

This means the story is not the single source of truth for its ADR and Journey dependencies. Developers have to manually cross-reference the runbook, Notion sync may be incomplete, and impact analysis tooling that reads the story file misses these relationships.

## User Story

As a **Platform Developer**, I want **`agent new-runbook` to extract ADR and Journey references from the generated runbook and write them back to the parent story file** so that **the story is always an accurate, up-to-date record of its architectural dependencies and affected journeys.**

## Acceptance Criteria

- [ ] **AC-1 — Extract ADR references**: After a runbook is successfully generated (schema + code gates passed), `new-runbook` scans the runbook content for all `ADR-\d+` references using a regex and deduplicates them.

- [ ] **AC-2 — Extract Journey references**: After a runbook is successfully generated, `new-runbook` scans the runbook content for all `JRN-\d+` references and deduplicates them.

- [ ] **AC-3 — Back-populate story `## Linked ADRs`**: Identified ADR references are merged into the parent story's `## Linked ADRs` section. Entries already present in the story are not duplicated. The ADR title/description is looked up from `.agent/docs/adrs/ADR-NNN*.md` — if the file **cannot be found, the reference is skipped** (the section remains `- None` rather than inserting a bare `ADR-NNN` that `agent implement` cannot validate). The section is updated in-place without touching any other part of the story file.

- [ ] **AC-4 — Back-populate story `## Linked Journeys`**: Identified Journey references are merged into the parent story's `## Linked Journeys` section. Entries already present are not duplicated. Journey title is looked up from the journey YAML's `name` field — if the file **cannot be found, the reference is skipped** (the section remains `- None`). Only resolvable references with a confirmed local file are written to the story.

- [ ] **AC-5 — Idempotent**: Running `new-runbook` a second time (regenerating) does not produce duplicate entries in the story.

- [ ] **AC-6 — No-op when empty**: If no ADR or Journey references appear in the runbook, the story file is not modified and no log noise is emitted.

- [ ] **AC-7 — Observability**: A structured log event `story_links_updated` is emitted containing `story_id`, `adrs_added: List[str]`, `journeys_added: List[str]`. If nothing was added, the event is not emitted.

- [ ] **Negative Test — Story file not writable**: If the story file cannot be written (permissions error), the command logs a warning and exits `0` — the runbook is still considered successfully generated; the back-population is best-effort.

- [ ] **Negative test — ADR dir missing**: If `.agent/docs/adrs/` does not exist, all ADR references are skipped (no entries added to the story; section stays `- None`); no error is raised.

## Non-Functional Requirements

- **Performance**: The extraction and file update must complete in < 200 ms (pure local I/O — no AI calls).
- **Atomicity**: The story file update uses a write-then-rename pattern to avoid partial writes.
- **Security**: No story content or runbook content is logged at INFO level or above during extraction.
- **Observability**: `story_links_updated` log event is structured with `extra=` dict per project conventions.

## Linked ADRs

- None

## Linked Journeys

- JRN-057: Impact Analysis Workflow

## Impact Analysis Summary

**Components touched:**
- `agent/commands/runbook.py` — **[MODIFY]** add post-generation ADR/Journey extraction and story back-population step
- `agent/commands/utils.py` — **[MODIFY]** add `extract_adr_refs(text)`, `extract_journey_refs(text)`, and `merge_story_links(story_file, adrs, journeys)` helpers with ID-based idempotency
- `agent/commands/tests/__init__.py` — **[NEW]** package init with Apache 2.0 header
- `agent/commands/tests/test_story_link_helpers.py` — **[NEW]** 17 unit tests covering all ACs and negative cases
- `CHANGELOG.md` — **[MODIFY]** add INFRA-158 entry under Unreleased
- `INFRA-156-preflight-finding-verification-gate.md` — **[MODIFY]** AC-6 and AC-7 added documenting the `agent implement` silent S/R mismatch failure mode discovered during INFRA-158 investigation

**Workflows affected:** `agent new-runbook` — purely additive post-processing step after successful generation.

**Risks identified:**
- Story file modification could corrupt an in-flight edit by a developer — mitigated by the write-then-rename atomicity requirement and the best-effort (non-blocking) failure mode.
- ADR title lookup requires a consistent filename convention (`ADR-NNN-*.md`) — if convention drifts, bare references are used gracefully.

## Test Strategy

- **Unit — `extract_adr_refs`**: Given runbook text containing `ADR-041`, `ADR-025` (duplicated), assert deduplicated set `{"ADR-041", "ADR-025"}` is returned.
- **Unit — `extract_journey_refs`**: Given runbook text with `JRN-057` referenced twice, assert `{"JRN-057"}`.
- **Unit — `merge_story_links` (happy path)**: Given a story with `## Linked ADRs\n\n- None`, assert it becomes `## Linked ADRs\n\n- ADR-041: Module Decomposition Standards`.
- **Unit — `merge_story_links` (idempotent)**: Given a story already listing `ADR-041`, assert no duplicate is added.
- **Unit — `merge_story_links` (no-op)**: Given empty ADR/Journey sets, assert story file is not modified.
- **Integration — end-to-end**: Mock AI to return a runbook containing `ADR-041` and `JRN-057`; assert the parent story file's sections are updated after `new_runbook` completes.
- **Negative test — unwritable story**: Mock `Path.write_text` to raise `PermissionError`; assert exit code is still `0` and a warning is logged.

## Rollback Plan

Remove the `extract_adr_refs`, `extract_journey_refs`, and `merge_story_links` helpers and delete the post-generation call in `runbook.py`. No schema or database changes are involved.

## Copyright

Copyright 2026 Justin Cook
