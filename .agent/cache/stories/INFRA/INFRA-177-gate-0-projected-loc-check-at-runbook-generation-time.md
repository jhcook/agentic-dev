# INFRA-177: Gate 0 — Projected LOC Check at Runbook Generation Time

## State

COMMITTED

## Problem Statement

The existing forecast gate (`score_story_complexity`) estimates LOC from story checkbox count using `step_count * 40 * verb_intensity`. It has no awareness of the actual on-disk file sizes being modified. A `[MODIFY]` block adding 50 lines to an already-850-line file costs nothing in the heuristic estimate, but triggers the post-apply LOC gate. INFRA-145's `orchestrator.py` reached 872 LOC this way — the complexity gate only fired after `--apply`, leaving the branch in `REVIEW_NEEDED` and requiring a full revert.

## User Story

As a developer running `agent new-runbook`, I want the pipeline to detect when a `[MODIFY]` or `[NEW]` block would push a file over the 500-line limit, so that I receive a correction prompt before the runbook is accepted — not after `--apply` has already been executed.

## Acceptance Criteria

- [ ] **AC-1**: Given a `[MODIFY]` block targeting a file whose current LOC plus the net line delta of the S/R replacement exceeds 500, `run_generation_gates()` returns a correction prompt instructing the AI to split the change into a separate module.
- [ ] **AC-2**: Given a `[NEW]` block whose code fence contains more than 500 lines, `run_generation_gates()` returns a correction prompt.
- [ ] **AC-3**: Given a `[MODIFY]` block where the projected LOC is ≤ 500, the gate passes with no correction prompt.
- [ ] **AC-4**: If the target file does not exist on disk (e.g. a new file incorrectly marked `[MODIFY]`, already handled by the S/R gate), this gate is a no-op for that block.
- [ ] **AC-5**: The LOC limit is read from `config.max_file_loc` (default 500) so it tracks the same threshold as the post-apply complexity check.
- [ ] **AC-6 — Gate 1b (malformed [MODIFY] detection)**: When a `[MODIFY]` block contains a fenced code block but is missing `<<<SEARCH/===/>>>` markers, `run_generation_gates()` returns a correction prompt instructing the AI to replace the bare code block with a proper S/R diff. This wires the existing `detect_malformed_modify_blocks` parser utility (which previously only logged a warning) into the correction loop so the AI gets actionable feedback.


## Non-Functional Requirements

- Performance: File reads are buffered; line counting via `str.count('\n')` not `len(splitlines())` for speed.
- Observability: Emit `projected_loc_gate_fail` with `file`, `current_loc`, `delta_loc`, `projected_loc` attributes.
- Accuracy: Net delta = lines in REPLACE minus lines in SEARCH (conservative; does not account for whitespace-only lines).

## Linked ADRs

- ADR-046 (Observability)

## Linked Journeys

- JRN-023

## Impact Analysis Summary

Components touched:
- `agent/core/implement/loc_guard.py` — **[NEW]** Contains `check_projected_loc` (Gate 0) and `CodeBlock` TypedDict. Extracted to keep `guards.py` under the 1000-line hard limit.
- `agent/core/implement/guards.py` — Re-exports `check_projected_loc` from `loc_guard` for backward compatibility.
- `agent/commands/runbook_gates.py` — Wires Gate 0 (LOC check) and Gate 1b (malformed `[MODIFY]` detection via `detect_malformed_modify_blocks`) into `run_generation_gates()`. Hoists `parse_code_blocks()` to a single shared call.

Workflows affected: `agent new-runbook` generation loop.
Risks identified: Over-counting due to trailing newline — mitigated by stripping search/replace text before counting.


## Test Strategy

- Unit — `check_projected_loc`: MODIFY that projects to 510 LOC on a 490-line file → correction
- Unit — `check_projected_loc`: MODIFY that projects to 480 LOC → pass
- Unit — `check_projected_loc`: NEW block with 520-line code fence → correction
- Unit — `check_projected_loc`: NEW block with 50-line code fence → pass
- Unit — `check_projected_loc`: MODIFY target file does not exist → no-op
- Integration — `run_generation_gates` with an over-budget MODIFY → correction_parts contains LOC warning

## Rollback Plan

Remove the `check_projected_loc` call from `run_generation_gates`. Purely additive check; no state mutation.

## Copyright

Copyright 2026 Justin Cook
