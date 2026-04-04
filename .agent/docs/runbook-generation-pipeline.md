# Runbook Generation Pipeline

> Last updated: INFRA-182 (2026-04-04)

This document describes the end-to-end flow of `agent new-runbook <STORY_ID>` in
its final phased-generation form. It covers every gate, post-processor, and
validation layer in the order they execute.

---

## Overview

```
[Story File]
     │
     ▼
[0] Pre-flight Gates
     │  • Story must be COMMITTED
     │  • Forecast gate (LOC/step/file budget)
     │
     ▼
[1] Context Assembly
     │  • Dynamic rule diet (ChromaDB semantic retrieval)
     │  • Targeted introspection — Pass 1a: backtick paths with slash
     │  •                          Pass 1b: bare backtick filenames (INFRA-182)
     │  • Test impact matrix
     │  • Behavioral contracts
     │  • Source tree + code outlines
     │
     ▼
[2] Phase 1 — Skeleton Generation (AI)
     │  • Single LLM call produces the step-header skeleton JSON
     │  • Checkpoint written to <runbook>.partial
     │
     ▼
[3] Phase 2c — Block Assembly (parallel AI, one call per step)
     │  For each skeleton step:
     │    • Vector shard queried for relevant context
     │    • Step prompt built with prior-change context
     │    • AI generates structured JSON ops block
     │    • [NEW]-on-existing guard → regenerate with [MODIFY] correction
     │    • Block appended to assembled_content
     │    • Checkpoint updated after every block
     │
     ▼
[4] Post-Generation Normalisation Passes  (order is significant)
     │
     │  1. _ensure_modify_blocks_fenced(assembled_content)
     │       Wraps bare [MODIFY] blocks in code fences.
     │
     │  2. _dedup_modify_blocks(assembled_content)
     │       Enforces one-file-one-block rule; merges or removes duplicates.
     │
     │  3. _escape_dunder_paths(assembled_content)
     │       Escapes __init__.py paths so the markdown parser sees them correctly.
     │
     │  4. _rebalance_fences(assembled_content)
     │       Deterministically closes orphaned code fences per step block.
     │
     │  5. _normalize_list_markers(assembled_content)
     │       * → -, double-space → single-space (MD004/MD030).
     │
     │  6. _fix_changelog_sr_headings(assembled_content)         ← INFRA-182
     │       • Case 1: # Changelog → ## [Unreleased] (avoids MD024/MD025)
     │       • Case 2: ## [Unreleased] → ## [Unreleased] (Updated by story)
     │                 by reading the actual first unreleased heading from disk,
     │                 so SEARCH anchors match the real file regardless of prior
     │                 story runs.
     │
     │  7. _ensure_blank_lines_around_fences(assembled_content)
     │       Inserts blank lines before/after fences (MD031).
     │
     │  8. validate_and_correct_sr_blocks(assembled_content)     ← INFRA-182
     │       Generation-time S/R verbatim pass (safety net).
     │       • Parses every [MODIFY] section header
     │       • Reads each target file from disk (repo_root)
     │       • Fuzzy-matches (threshold 0.7) AI-generated SEARCH text
     │         against actual file content; replaces on match
     │       • Emits sr_final_pass_complete structured log event
     │       • Exceptions are caught and logged as sr_final_pass_error
     │         (generation continues — gate below is the hard stop)
     │
     ▼
[5] _write_and_sync (runbook.py)
     │
     │  Layer 0 — Fence autocorrect
     │       autocorrect_runbook_fences(content)
     │       Fixes malformed opening/closing fences; logs auto-fixed items.
     │
     │  Layer 1 — Fuzzy + AI S/R correction  (validate_and_correct_sr_blocks)
     │       threshold: 0.80
     │       Reports "N block(s) checked, M auto-corrected"
     │
     │  Layer 2 — Hard gate  (validate_sr_blocks / _lines_match)        ← INFRA-182
     │       For each [MODIFY] block:
     │         • Reads target file from disk
     │         • Calls _lines_match(search_text, file_text)
     │             – Both sides fully stripped (leading + trailing) per line
     │             – Sliding window match: len(search_lines) lines at a time
     │         • On any real mismatch → sr_hard_gate_failed + Exit(1)
     │       Skips:
     │         • .agent/cache/ paths (runbooks, stories, plans)
     │         • missing_modify entries (file not yet on disk)
     │         • parse_error entries (invalid path, skipped by parser)
     │
     │  Layer 3 — Lint gate  (lint_runbook_syntax)
     │       Structural markdown lint check; failures → Exit(1).
     │
     │  ── All gates passed ──
     │
     │  • Trailing newline normalisation
     │  • runbook_file.write_text(content)
     │  • markdownlint --fix (trailing whitespace, blank lines, etc.)
     │  • Back-populate story ADRs + Journeys  (merge_story_links / INFRA-158)
     │  • upsert_artifact → local cache sync
     │
     ▼
[6] Done — runbook written, story links updated
```

---

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `commands/runbook.py` | CLI entry point, context assembly, path to `_write_and_sync` |
| `commands/runbook_generation.py` | Phase 1 + Phase 2c generation loop, all post-processors |
| `commands/runbook_gates.py` | Generation-time schema/code/S/R/DoD gate orchestration |
| `commands/utils.py` | `validate_sr_blocks`, `_lines_match`, auto-fix helpers |
| `core/implement/sr_validation.py` | `validate_and_correct_sr_blocks` (fuzzy + AI reanchor) |
| `core/implement/parser.py` | `parse_search_replace_blocks` (path-safe section splitter) |
| `core/context.py` | `_load_targeted_context` (Pass 1a + Pass 1b introspection) |

---

## S/R Validation Layers (Summary)

| Layer | Where | Mechanism | Threshold |
|-------|-------|-----------|-----------|
| 0 | `_write_and_sync` | Fence autocorrect | deterministic |
| 1 | `_write_and_sync` | Fuzzy + AI reanchor (`validate_and_correct_sr_blocks`) | 0.80 similarity |
| 2 | `_write_and_sync` | Hard gate (`_lines_match` with full strip) | exact / whitespace-normalized |
| Safety net | `generate_runbook_chunked` | Same fuzzy pass at generation time (INFRA-182) | 0.7 similarity |

**Layer 2 (`_lines_match`) behaviour:** Both the SEARCH block and each candidate
file window are stripped of leading *and* trailing whitespace on every line before
comparison. This absorbs constant-indent drift (AI writes `# comment` but the
actual file has `    # comment` inside a function body) without false positives on
code where indentation is semantically significant — because the sliding window
ensures structural position is preserved.

---

## CHANGELOG SEARCH Normalisation

CHANGELOG entries are a persistent source of drift because each story run changes
the `## [Unreleased]` heading to `## [Unreleased] (Updated by story)`.
`_fix_changelog_sr_headings` handles this at post-generation time by:

1. Rewriting AI-generated `# Changelog` anchors to `## [Unreleased]` (MD024/MD025 fix).
2. Reading the **actual** first `## [Unreleased]...` line from `CHANGELOG.md` on
   disk and substituting it into SEARCH blocks that used the bare form, so the
   block is always verbatim-correct regardless of how many prior stories have run.

---

## Introspection: Pass 1a + 1b

`_load_targeted_context` extracts file paths from the story Impact Analysis and
injects their full contents into the generation prompt.

| Pass | Pattern matched | Example |
|------|----------------|---------|
| 1a | Backtick path containing `/` | `` `.agent/src/agent/commands/runbook_generation.py` `` |
| 1b | Bare backtick filename (no slash) | `` `runbook_generation.py` `` → resolved via `rglob` |

Without Pass 1b (pre-INFRA-182), bare filenames in the Impact Analysis were
silently dropped, reducing introspection from ~99 KB to ~5 KB.

---

## Parser Resilience: Invalid Paths

`parse_search_replace_blocks` catches `ParsingError` per file section and skips
the section with a `DEBUG` log rather than propagating the exception. This prevents
AI-generated code fragments (e.g. `"):`) from being parsed as file paths and
crashing the entire `_write_and_sync` pipeline.
