# INFRA-172: Per-Section Vector Query for Runbook Block Generation

## State

DRAFT

## Problem Statement

The runbook block generation pipeline currently builds `context_summary` once — a static
blob combining `source_tree`, `source_code`, a single upfront vector query result
(`targeted_context`), and `rules_content` — and passes the same context to every block
prompt across all sections (e.g. Architecture & Design, Security, Observability, etc.).

This means:
- A Security section prompt receives the same file chunks as an Observability section.
- Files relevant to a specific section (e.g. `gates.py` for a Security block) may not
  surface in the global query, leading to AI hallucination in `<<<SEARCH` blocks.
- The global `modify_file_contents` oracle is a workaround (section-scoped file injection)
  but relies on the AI skeleton's `files` list, which is itself incomplete.

The correct fix is a **per-section vector query**: each block generation prompt queries
Chroma with the section title + description as the query string, retrieving the most
relevant file chunks for that specific section's intent.

A secondary consequence of the global context blob is **block prompt size bloat**: the
entire `source_code` outline + `rules_content` + `source_tree` is injected into every
block prompt regardless of relevance. This directly causes Gemini API timeouts (observed
at 300–420s on block 1/8) when the combined prompt exceeds the model's practical latency
cap. Per-section queries, by replacing the monolithic blob with targeted chunks, are
expected to reduce per-block prompt size by ~60–80% and eliminate timeout failures.

## User Story

As an agent running `new-runbook`, I want each block prompt to receive context from a
targeted vector query scoped to that section's intent, so that `<<<SEARCH` blocks are
grounded in the correct, relevant source code and hallucination rates decrease.

## Acceptance Criteria

- [ ] **AC-1**: Before generating each block, the pipeline issues a Chroma vector query
      using `f"{section.title}: {section.description}"` as the query string.
- [ ] **AC-2**: The per-section query results replace (or supplement) the global
      `targeted_context` in `context_summary` for that block's prompt only.
- [ ] **AC-3**: The global upfront query is retained as a fallback when Chroma is
      unavailable or returns no results for a section query.
- [ ] **AC-4**: A structured log event `section_context_loaded` is emitted per section
      with `section_title`, `chunk_count`, and `query_latency_ms`.
- [ ] **AC-5**: The per-section query respects the same `k` (top-k chunks) limit as the
      existing global query to avoid context overflow.
- [ ] **AC-6**: Unit tests cover the per-section query call, fallback behavior, and the
      structured log event.
- [ ] **AC-7**: S/R hallucination rate (measured by `sr_corrected / sr_total` in the
      `_write_and_sync` log output) does not increase vs. the current baseline across a
      test corpus of 3+ runbook generations.
- [ ] **AC-8**: Per-block prompt size (measured in characters) is ≤ 50% of the current
      global-context baseline, verified via the `block_prompt_chars` structured log field
      added in this story.

## Non-Functional Requirements

- **Performance**: Per-section query adds at most 500ms per section (Chroma is local).
- **Observability**: `section_context_loaded` spans nested under `runbook.block_generation`.
- **Compliance**: No PII in query strings (story content may be scrubbed if needed).

## Linked ADRs

- ADR-012 (Code Complexity Gates)
- ADR-025 (Local Import Pattern)

## Linked Journeys

- JRN-089 (generate-runbook-with-targeted-codebase-introspection)

## Impact Analysis Summary

Components touched:
- `.agent/src/agent/commands/runbook_generation.py`
- `.agent/src/agent/core/ai/prompts.py` (context_summary parameter may evolve)
- `.agent/tests/commands/tests/test_runbook_generation.py` (new unit tests)

Workflows affected: `agent new-runbook`
Risks identified: Per-section queries increase total generation time by ~N × 500ms where
N = number of sections. Mitigated by local Chroma latency being sub-100ms typically.

## Test Strategy

- Unit: mock Chroma client, assert per-section query is called with correct query string.
- Unit: assert fallback to global context when Chroma returns empty results.
- Integration: run `agent new-runbook` on a test story and verify `sr_corrected` count
  does not regress vs. baseline.

## Rollback Plan

Feature-flagged via `USE_PER_SECTION_CONTEXT=true` env var. Revert by unsetting the flag —
the global upfront query path remains unchanged as the fallback.

## Copyright

Copyright 2026 Justin Cook
