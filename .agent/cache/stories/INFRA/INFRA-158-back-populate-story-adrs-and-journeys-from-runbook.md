# INFRA-158: Back-Populate Story with ADRs and Journeys Identified During Runbook Generation

## State

COMMITTED

## Problem Statement

When `agent new-runbook` generates a runbook, the AI Governance Panel often identifies relevant Architectural Decision Records (ADRs) and User Journeys that the implementation must respect or extend. These references appear in the runbook under `## Linked Journeys` and `## Panel Review Findings` — but they are never written back to the parent story. The story's `## Linked ADRs` and `## Linked Journeys` sections remain empty (or contain `None`) even though the runbook has populated those fields with concrete references.

This means the story is not the single source of truth for its ADR and Journey dependencies. Developers have to manually cross-reference the runbook, Notion sync may be incomplete, and impact analysis tooling that reads the story file misses these relationships.

## User Story

As a **Platform Developer**, I want **`agent new-runbook` to extract ADR and Journey references from the generated runbook and write them back to the parent story file** so that **the story is always an accurate, up-to-date record of its architectural dependencies and affected journeys.**

## Acceptance Criteria

- [x] **AC-1 — Extract ADR references**: After a runbook is successfully generated (schema + code gates passed), `new-runbook` scans the runbook content for all `ADR-\d+` references using a regex and deduplicates them.

- [x] **AC-2 — Extract Journey references**: After a runbook is successfully generated, `new-runbook` scans the runbook content for all `JRN-\d+` references and deduplicates them.

- [x] **AC-3 — Back-populate story `## Linked ADRs`**: Identified ADR references are merged into the parent story's `## Linked ADRs` section. Entries already present in the story are not duplicated. The ADR title/description is looked up from `.agent/docs/adrs/ADR-NNN*.md` — if the file **cannot be found, the reference is skipped** (the section remains `- None` rather than inserting a bare `ADR-NNN` that `agent implement` cannot validate). The section is updated in-place without touching any other part of the story file.

- [x] **AC-4 — Back-populate story `## Linked Journeys`**: Identified Journey references are merged into the parent story's `## Linked Journeys` section. Entries already present are not duplicated. Journey title is looked up from the journey YAML's `name` field — if the file **cannot be found, the reference is skipped** (the section remains `- None`). Only resolvable references with a confirmed local file are written to the story.

- [x] **AC-5 — Idempotent**: Running `new-runbook` a second time (regenerating) does not produce duplicate entries in the story.

- [x] **AC-6 — No-op when empty**: If no ADR or Journey references appear in the runbook, the story file is not modified and no log noise is emitted.

- [x] **AC-7 — Observability**: A structured log event `story_links_updated` is emitted containing `story_id`, `adrs_added: List[str]`, `journeys_added: List[str]`. If nothing was added, the event is not emitted.

- [x] **Negative Test — Story file not writable**: If the story file cannot be written (permissions error), the command logs a warning and exits `0` — the runbook is still considered successfully generated; the back-population is best-effort.

- [x] **Negative test — ADR dir missing**: If `.agent/docs/adrs/` does not exist, all ADR references are skipped (no entries added to the story; section stays `- None`); no error is raised.

## Non-Functional Requirements

- **Performance**: The extraction and file update must complete in < 200 ms (pure local I/O — no AI calls).
- **Atomicity**: The story file update uses a write-then-rename pattern to avoid partial writes.
- **Security**: No story content or runbook content is logged at INFO level or above during extraction.
- **Observability**: `story_links_updated` log event is structured with `extra=` dict per project conventions.

## Linked ADRs

- ADR-099: Top-Level Test Directory Layout and PYTHONPATH=src Configuration

## Linked Journeys

- JRN-057: Impact Analysis Workflow

## Impact Analysis Summary

**Components touched:**
- `agent/commands/runbook.py` — **[MODIFY]** add post-generation ADR/Journey extraction and story back-population step
- `agent/commands/utils.py` — **[MODIFY]** add `extract_adr_refs(text)`, `extract_journey_refs(text)`, and `merge_story_links(story_file, adrs, journeys)` helpers with ID-based idempotency
- `.agent/tests/commands/__init__.py` — **[NEW]** package init with Apache 2.0 header
- `.agent/tests/commands/test_story_link_helpers.py` — **[NEW]** 17 unit tests covering all ACs and negative cases
- `.agent/tests/integration/test_agent_integration.py` — **[MODIFY]** optimize memory copying to fix integration test suite RAM exhaustion
- `.agent/tests/journeys/test_infra_077.py` — **[MODIFY]** update test expectations due to GDPR cookie extraction disablement
- `.agent/tests/journeys/test_jrn_001.py` — **[MODIFY]** fix infinite pytest recursion loop
- `.agent/tests/commands/test_basic_commands.py` — **[MODIFY]** resolve cache directory pollution issue in pr command tests
- `CHANGELOG.md` — **[MODIFY]** add INFRA-158 entry under Unreleased
- `INFRA-156-preflight-finding-verification-gate.md` — **[MODIFY]** AC-6 and AC-7 added documenting the `agent implement` silent S/R mismatch failure mode discovered during INFRA-158 investigation
- `.agent/tests/commands/test_runbook.py` — **[MODIFY]** Update integration tests and mock behaviors to align with the new pipeline, fixing legacy assertions.
- `.agent/pyproject.toml` — **[MODIFY]** add new production dependencies `beautifulsoup4==4.14.3` and `markdownify==1.2.2` (required by `merge_story_links` HTML→markdown conversion); add new dev dependency `pytest-timeout` (prevents keychain-blocking test hangs in CI)
- `.agent/docs/adrs/ADR-099-test-directory-layout-and-pythonpath-configuration.md` — **[NEW]** formal ADR documenting the `.agent/tests/` top-level layout and `PYTHONPATH=src` configuration co-committed in this branch

**Out-of-scope but co-committed changes:**
- **INFRA-094 and others**: Multiple tests and files modified/added in this branch (`.agent/tests/journeys/test_jrn_*.py`, `.agent/tests/commands/test_runbook_split_request.py`, `.agent/tests/governance/test_syntax_validation.py`, `.agent/src/agent/commands/check.py`, etc.) are explicitly noted as out-of-scope but co-committed to finalize the branch preflight.
- **CI configuration update**: Added `--ignore` flags for `tests/voice`, `tests/backend`, `tests/integration`, and `tests/e2e` to the preflight test command in `agent.yaml`. These directories import torch/FastAPI at module level causing OOM kills when combined with agent framework tests in a single pytest process. The rationale is documented inline in `agent.yaml`. No ADR required — this is an operational CI scoping decision, not an architectural one.
- **Runbook Parser & Credentials**: A refactor of the runbook parser, AI provider engine (`ai_provider.py`), and credential handling systems (`credentials.py`) was also co-committed as an out-of-scope improvement.
- **`.agent/src/agent/tools/context.py`**: Two functional fixes co-committed from a prior branch: (1) `checkpoint()` now returns early with a success result when the working tree is clean ("No local changes to save"), preventing a silent no-op; (2) `rollback()` now runs `git clean -fd` between `git reset --hard` and `git stash apply` to remove untracked files before restoring state, and adds `capture_output=True` to all subprocess calls for cleaner error handling.
- **`.agent/src/agent/tools/custom/test_override.py`**: Accidentally committed scratch file (contained `os.system('ls')`). **Deleted in this branch** — it should never have been committed.

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
