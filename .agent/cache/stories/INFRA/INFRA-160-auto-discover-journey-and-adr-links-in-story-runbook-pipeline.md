# INFRA-160: Inject Journey + ADR Catalogue Into Runbook Generation Prompt

## State

DRAFT

## Problem Statement

The `agent new-runbook` AI prompt does not include the list of available Journeys (`JRN-NNN`)
or ADRs (`ADR-NNN`) that exist in the project. Without this catalogue, the AI panel cannot
reference them by ID — it defaults to `## Linked Journeys: - None` even for stories that clearly
touch existing workflows.

The downstream consequence is that `merge_story_links` (INFRA-158) has nothing to back-populate
into the story, leaving `## Linked Journeys: - None`, causing `agent implement` to fail the
journey gate. The developer must manually intervene — contradicting the promise that the CLI
is fully self-sufficient.

The correct data flow is:
```
agent new-runbook
  → AI prompt includes JRN/ADR catalogue
  → AI identifies and references JRN-089, JRN-056, ADR-041 etc. in generated runbook
  → merge_story_links back-populates story (INFRA-158)
  → agent implement journey gate passes automatically
```

The story is the author's intent. The runbook is the technical source of truth. All relevant
technical metadata (journeys, ADRs) must flow *from the runbook back to the story*, not be
guessed at story creation time.

## User Story

As a **Platform Developer**, I want **`agent new-runbook` to include the full list of available
Journeys and ADRs in the AI generation prompt** so that **the AI panel can identify and reference
the relevant ones by ID, which are then automatically back-populated into the story via
`merge_story_links`, ensuring the journey gate never fails due to missing metadata.**

## Acceptance Criteria

- [ ] **AC-1 — JRN catalogue in prompt**: Before calling the AI, `new-runbook` scans
  `.agent/cache/journeys/` recursively for all `JRN-NNN-*.yaml` files. For each file, it reads
  the `id` and `title` fields. This catalogue is injected into the system prompt as a structured
  list (e.g., `Available Journeys:\n- JRN-056: Full Implementation Workflow\n...`).

- [ ] **AC-2 — ADR catalogue in prompt**: Same as AC-1 but for ADRs — scans
  `config.adrs_dir` for `ADR-NNN-*.md` files and reads the H1 title from each. Injected as
  `Available ADRs:\n- ADR-041: Module Decomposition Standards\n...`.

- [ ] **AC-3 — Story links pre-seeded**: If the story already has non-`None` entries in
  `## Linked Journeys` or `## Linked ADRs`, these are also included in the prompt so the AI
  preserves and builds on them rather than overwriting them with `None`.

- [ ] **AC-4 — Journey gate always satisfiable**: After this change, running
  `agent new-story <ID>` followed by `agent new-runbook <ID>` on a story that touches an
  existing workflow must produce a runbook that identifies at least one journey — no manual
  editing required for the journey gate to pass.

- [ ] **AC-5 — Token budget**: The catalogue is limited to the top 30 entries (sorted by
  numeric ID, most recent first) to avoid bloating the prompt. Only `id` and `title` are
  included — no full YAML bodies.

- [ ] **AC-6 — Graceful fallback**: If the journeys or ADRs directory does not exist or is
  empty, the catalogue section is omitted from the prompt and a debug log is emitted. Story
  creation and runbook generation still succeed.

- [ ] **AC-7 — Observability**: Structured log event `catalogue_injected` is emitted with
  `story_id`, `journey_count: int`, `adr_count: int` before each generation attempt.

## Non-Functional Requirements

- **Performance**: File scanning must complete in < 100 ms (directory listing + YAML `id`/`title`
  reads only — no full file parsing).
- **Security**: File content is not logged at INFO level or above.
- **Token overhead**: The catalogue adds approximately 1–2k tokens per generation attempt
  (30 entries × ~50 chars each). Acceptable given existing prompt sizes.

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight
- ADR-040: Agentic Tool-Calling Loop Architecture

## Linked Journeys

- JRN-056: Full Implementation Workflow
- JRN-089: Generate Runbook with Targeted Codebase Introspection

## Impact Analysis Summary

**Components touched:**
- `agent/commands/runbook.py` — **[MODIFY]** build and inject JRN/ADR catalogue into `user_prompt`
  before the generation loop
- `agent/commands/utils.py` — **[MODIFY]** add `build_journey_catalogue(journeys_dir)` and
  `build_adr_catalogue(adrs_dir)` helpers returning formatted strings
- `agent/commands/tests/test_story_link_helpers.py` — **[MODIFY]** add unit tests for
  catalogue builder helpers

**Workflows affected:** `agent new-runbook` — prompt augmentation only, no change to output
format or saving logic.

**Risks identified:**
- Token overhead bloats the prompt; mitigated by the top-30 cap and title-only extraction.
- AI may reference non-existent journey IDs if the catalogue is stale; mitigated because
  `merge_story_links` already validates that identified JRN files exist on disk before writing.

## Test Strategy

- **Unit — `build_journey_catalogue`**: Given a temp dir with three JRN YAMLs, assert the
  returned string lists all three in `- JRN-NNN: Title` format sorted by ID descending.
- **Unit — `build_adr_catalogue`**: Same pattern for ADR markdown files.
- **Unit — top-30 cap**: Given 35 JRN files, assert only 30 appear in the output.
- **Unit — empty dir**: Assert empty string returned when directory is empty or missing.
- **Integration — prompt injection**: Mock `config.journeys_dir` and assert the generated
  prompt passed to the AI contains the `Available Journeys:` section.
- **Integration — journey gate**: After `new-runbook`, assert that the story's
  `## Linked Journeys` has at least one non-None entry (relies on INFRA-158 back-population).

## Rollback Plan

Remove the catalogue build calls from `runbook.py` and delete the two helper functions.
No schema or file-format changes.

## Copyright

Copyright 2026 Justin Cook
