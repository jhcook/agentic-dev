# INFRA-096: Safe Implementation Apply

## State

COMMITTED

## Problem Statement

The `agent implement` pipeline has three compounding design flaws that repeatedly destroy existing code when applying AI-generated changes:

1. **Prompt demands "Complete file content"** — The system prompt (implement.py L607) tells the AI to produce entire files, not diffs. For large files (gates.py: 554 LOC, implement.py: 920 LOC), the AI cannot faithfully reproduce existing code and instead rewrites it from scratch, dropping hundreds of lines.
2. **No source context injected** — The user prompt sends the runbook, governance rules, and ADRs, but **never the current contents** of files being modified. The AI cannot produce accurate diffs without seeing what it's editing.
3. **Blind `write_text()` overwrite** — `apply_change_to_file()` calls `file_path.write_text(content)` unconditionally, replacing the entire file with whatever the AI outputs. No merge, no diff detection, no conflict resolution.

These three issues compound: the AI has no context, so it fabricates the file; the prompt tells it to produce complete files, reinforcing that fabrication; and the apply function treats that fabrication as authoritative, wiping the real code.

**Observed incidents:**
- INFRA-093 implementation: Lost ~1,400 lines across gates.py, implement.py, runbook.py
- INFRA-092 implementation: Deleted runbooks entirely
- Multiple prior incidents of similar destruction

This is Layer 2b of the INFRA-089 defence-in-depth strategy, complementing INFRA-094 (SPLIT_REQUEST fallback at layer 2a).

## User Story

As a **developer using the agentic-dev framework**, I want **the implementation pipeline to use diff-based apply with source context injection** so that **existing code is never destructively overwritten during AI-driven implementation**.

## Acceptance Criteria

### Diff-Based Output
- [ ] **AC-1 (Diff-Based Prompt)**: The implementation system prompt instructs the AI to emit search/replace blocks for existing files. Format:

  ```
  <<<SEARCH
  exact lines to find
  ===
  replacement lines
  >>>
  ```

  Full-file output remains allowed for new files only.

### Source Context Injection
- [ ] **AC-2 (Source Context)**: When the runbook references existing files (via `[MODIFY]` markers), the current file content is included in the user prompt so the AI knows what it's editing.
- [ ] **AC-3 (Context Truncation)**: Files exceeding 300 LOC are truncated to first/last 100 lines with an `... ({N} lines omitted)` marker to manage token pressure.

### Merge-Aware Apply
- [ ] **AC-4 (Apply Strategy Detection)**: `apply_change_to_file()` detects whether AI output is:
  - Full file content → allowed only for new files
  - Search/replace blocks → applied surgically to existing content
- [ ] **AC-5 (File Size Guard)**: Existing files above a configurable threshold (default: 200 LOC) **reject** full-file overwrites. The AI must use search/replace format.
- [ ] **AC-6 (Match Failure Handling)**: If a search block doesn't match existing content, the change is rejected with a clear error message (no silent failure, no partial apply).

### Backward Compatibility
- [ ] **AC-7 (New Files)**: New files (not yet on disk) continue to accept full-file content.
- [ ] **AC-8 (Legacy Flag)**: A `--legacy-apply` flag bypasses the new protections for escape-hatch use cases, with `log_skip_audit` called.

## Non-Functional Requirements

- Compliance: Structured logging for apply decisions (`apply_mode`, `file`, `lines_changed`) for SOC2.
- Observability: OpenTelemetry spans for `apply_change`, `parse_search_replace`, `inject_source_context`.
- Performance: Source context injection must stay within AI context window limits. Token budget accounting should warn if total prompt exceeds 80% of provider's context window.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-064 — Forecast-Gated Story Decomposition

## Related Stories

- INFRA-089 — Enforce Atomic Development (parent defence-in-depth plan)
- INFRA-093 — Forecast Gate for Runbook Generation (Layer 1 — heuristic pre-check)
- INFRA-094 — SPLIT_REQUEST Fallback (Layer 2a — runbook generation guard)

## Impact Analysis Summary

Components touched: `implement.py` (system prompt, `apply_change_to_file`, `parse_code_blocks`)
Workflows affected: `/implement`
Risks:
- AI may not reliably produce search/replace blocks. Malformed output must be handled gracefully — fall back to rejection, not silent overwrite.
- Search/replace blocks may fail to match if the AI hallucinates existing content. Fuzzy matching is dangerous; strict match + clear rejection is safer.
- Source context adds token pressure. For the chunking fallback, per-chunk source context for each referenced file must be included.
- The chunked processing path (lines 668–739) must also be updated to use the new prompt and apply logic.

## Test Strategy

- Unit: New file with full content → accepted and written
- Unit: Existing file (>200 LOC) with full content → **rejected** with warning
- Unit: Existing file with search/replace blocks → applied surgically, content verified
- Unit: Search/replace block with no match → rejected with clear error message
- Unit: Multiple search/replace blocks in one response → all applied in order
- Unit: Source context injection → file content appears in user prompt
- Unit: Large file source context → truncated to head/tail with omission marker
- Unit: `--legacy-apply` flag → bypasses protections, audit logged
- Integration: End-to-end implement with diff-based apply on a real 500+ LOC file

## Rollback Plan

Revert prompt and apply changes in `implement.py` and related tests. The `--legacy-apply` flag serves as an in-place escape hatch. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
