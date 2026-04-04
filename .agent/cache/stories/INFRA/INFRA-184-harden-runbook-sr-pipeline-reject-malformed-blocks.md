# INFRA-184: Harden Runbook S/R Pipeline: Reject Malformed Blocks Before Gate

## State

COMMITTED

## Problem Statement

The `agent new-runbook` pipeline frequently generates malformed S/R blocks that cause the entire 
implementation workflow to stall — costing multiple manual intervention steps per story. Two 
distinct failure modes have been observed repeatedly:

**Failure Mode 1: Empty SEARCH blocks (`<<<SEARCH\n\n===`)**
The LLM generates S/R blocks with an empty SEARCH section. The S/R syntax gate
(`_sr_check_replace_syntax` in `utils.py`) passes these to `str.replace("", x, 1)`, which
prepends the REPLACE content to the entire file — producing broken AST output and false
"syntax advisory" warnings for every affected file. INFRA-146 triggered 22 such warnings across
all 15 voice tool files, requiring manual regex cleanup of the runbook before implementation
could proceed.

**Failure Mode 2: Schema rejection of empty `function-after` lists**
The runbook schema validator rejects blocks where `function-after.blocks` is an empty list,
raising `List should have at least 1 item after validation, not 0`. This is a schema constraint
that the LLM violates when it omits `function-after` content, causing `agent implement` to refuse
to apply any changes at all.

Both failures are caught only at implementation time, after expensive LLM generation has completed.
The fixes belong at the parsing/validation layer — not as manual post-hoc runbook edits.

**Partial fix already landed**: `_sr_check_replace_syntax` in `utils.py` now returns `None` early
on empty `search_text` and emits `sr_replace_malformed_empty_search` instead of a false syntax
advisory. This story completes the hardening.

## User Story

As a **Platform Developer running `agent new-runbook`**, I want **malformed S/R blocks and schema
violations caught and auto-corrected at generation time**, so that **`agent implement` runs to
completion on the first attempt without requiring manual runbook edits.**

## Acceptance Criteria

- [ ] **AC-1**: Empty SEARCH block auto-correction: the runbook postprocessor strips
      `<<<SEARCH\n(whitespace)\n===\n` blocks from generated runbooks before writing to disk.
      Zero empty-SEARCH blocks survive into the saved runbook file.
- [ ] **AC-2**: LLM prompt guard: the generation prompt includes an explicit negative constraint:
      *"Never emit an empty `<<<SEARCH` block. If you have no search text, omit the block entirely."*
- [ ] **AC-3**: `function-after.blocks` schema autocorrection: if the schema validator encounters
      a `function-after` section with an empty `blocks` list, it either removes the section or
      populates it with the file's current content rather than hard-failing.
- [ ] **AC-4**: Parser-level early rejection: the S/R block parser
      (`agent.core.implement.parser`) emits a `sr_replace_malformed_empty_search` structured log
      event and skips the block entirely, rather than forwarding it to the syntax gate.
- [ ] **AC-5**: S/R validation report surface: `agent new-runbook` output prints a summary of
      malformed blocks skipped (count + file names) so the user knows what the LLM failed to
      generate correctly, without the alarming "syntax advisory" language.
- [ ] **Regression**: Running `agent new-runbook` against a story that targets the 15
      `backend/voice/tools/` files produces zero syntax advisories in a re-run.

## Non-Functional Requirements

- Autocorrection must be idempotent: running the postprocessor twice produces the same output.
- No functional regression to valid S/R blocks (non-empty SEARCH, valid Python output).
- LOC gate: no single file modified exceeds 1000 LOC after changes.

## Linked Journeys

- JRN-009: Enhance Implement Command — this story hardens the S/R parsing pipeline that JRN-009 exercises.

## Linked ADRs

- ADR-046: Structured Logging & Observability

## Impact Analysis Summary

- **`agent/commands/utils.py`**: AC-4 guard already landed (partial). Extend to cover
  postprocessor call chain.
- **`agent/commands/runbook_postprocess.py`**: AC-1 — add `strip_empty_sr_blocks()` pass.
- **`agent/commands/runbook_generation.py`**: AC-2 — add prompt constraint to generation system
  prompt.
- **`agent/core/implement/parser.py`**: AC-4 — emit structured log, skip block in parse loop.
- **`agent/commands/runbook_gates.py`** or CLI output: AC-5 — surface skipped-block summary.
- **Schema autocorrect** (`runbook_postprocess.py`): AC-3 — handle empty `function-after.blocks`.

## Test Strategy

- **Unit** (`test_runbook_postprocess.py`): `strip_empty_sr_blocks()` removes empty SEARCH
  blocks and is idempotent.
- **Unit** (`test_utils_sr_gate.py`): `_sr_check_replace_syntax("content", "", "x")` returns
  `None` (already passes post-INFRA-184 partial fix).
- **Unit** (`test_parser.py`): Parser yields no block for empty SEARCH input; emits
  `sr_replace_malformed_empty_search` log event.
- **Integration**: Re-run runbook generation against INFRA-146 story, assert zero syntax
  advisories in output.

## Rollback Plan

All changes are additive guards — removing them restores the previous (broken) behaviour.
No data migrations required.

## Copyright

Copyright 2026 Justin Cook
