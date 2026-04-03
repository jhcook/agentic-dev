# INFRA-180: REPLACE-Side Semantic Validation in validate_sr_blocks

## State

COMMITTED

## Problem Statement

`validate_sr_blocks` in `commands/utils.py` reads both `search` and `replace` from every S/R block (line 408–411), reads the full on-disk `file_text` (line 441), and uses all three to check whether the SEARCH matches. It then discards the REPLACE without inspecting it. This is the root cause of the INFRA-145 and INFRA-176 runbook failures:

1. **Hallucinated imports in implementation files**: The AI emits `from agent.core.implement.models import CodeBlock` in guards.py — a type that does not exist. No gate checks this.
2. **Function signature replacement**: The AI replaces a 10-arg function with a 3-arg stub. The REPLACE is syntactically valid Python, so the code gate passes. No gate checks that the REPLACE preserves the established public API.
3. **Stub regression**: The REPLACE is dramatically smaller than the SEARCH (300 lines → 15 lines), indicating the AI hallucinated a simplified version. No gate checks regression size.
4. **Re-anchoring blind spot**: When the SEARCH doesn't match, the re-anchoring loop corrects the SEARCH to match the real file — but leaves the hallucinated REPLACE unchanged. After re-anchoring, `validate_sr_blocks` reports `0 mismatches`, providing false confidence.

Because `validate_sr_blocks` already has SEARCH, REPLACE, and file_text available at the point where it evaluates each block, it is the correct and only place to add these checks. Adding them as outer gates is insufficient because outer gates don't see SEARCH and REPLACE together.

## User Story

As a developer running `agent new-runbook`, I want `validate_sr_blocks` to validate the REPLACE side of every `[MODIFY]` block — checking for projected syntax errors, unresolvable imports, function signature regressions, and stub replacements — so that a hallucinated REPLACE cannot pass the S/R gate and reach `--apply`.

## Acceptance Criteria

- [ ] **AC-1 — Projected syntax**: When a `[MODIFY]` REPLACE block would produce a `SyntaxError` when applied to the on-disk file, `validate_sr_blocks` returns a mismatch with `replace_syntax_error` key describing the error. The entry is treated as a real mismatch by the correction loop.
- [ ] **AC-2 — Import existence (implementation files)**: When a `[MODIFY]` REPLACE block for a `.py` file introduces a `from agent.X import Y` statement where `Y` does not exist on disk in the internal codebase, `validate_sr_blocks` returns a mismatch with `replace_import_error` key. The `other_defs` escape hatch is provided in the helper signature for future cross-block symbol resolution (deferred — not in scope for INFRA-180).
- [ ] **AC-3 — Function signature stability**: When a `[MODIFY]` REPLACE block for a `.py` file changes the parameter signature of a public function or class (detected by `ast` diff of SEARCH vs REPLACE), and no other block in the runbook updates callers of that function, `validate_sr_blocks` returns a mismatch with `replace_signature_error` key.
- [ ] **AC-4 — Stub regression guard**: When a `[MODIFY]` REPLACE block contains fewer than 25% of the LOC of the SEARCH block (configurable via `config.sr_stub_threshold`, default 0.25), `validate_sr_blocks` returns a mismatch with `replace_regression_warning` key.
- [ ] **AC-5 — Non-Python files are exempt from AC-1, AC-2, AC-3**: Only `.py` files are subject to syntax, import, and signature checks. LOC regression check (AC-4) applies to all file types.
- [ ] **AC-6 — Re-anchoring awareness**: The REPLACE-side checks must run even when the SEARCH was corrected by the re-anchoring loop, so that a corrected anchor with a bad REPLACE is still caught.
- [ ] **AC-7 — No false positives on intentional deletions**: If the REPLACE is empty and the `[MODIFY]` is removing a block entirely (REPLACE has 0 lines), the regression guard does not fire.

## Non-Functional Requirements

- Performance: All checks are in-memory; combined overhead per block must be <50ms. `ast.parse` on projected content is the bottleneck; acceptable for source files up to 10K LOC.
- Observability: Emit distinct structured log events for each check type: `sr_replace_syntax_fail`, `sr_replace_import_fail`, `sr_replace_signature_fail`, `sr_replace_regression_warn`.
- Compatibility: `validate_sr_blocks` return type `List[SRMismatch]` must remain unchanged — new keys are additive to the existing TypedDict.

## Linked ADRs

- ADR-046 (Observability — structured logging)

## Linked Journeys

- JRN-023

## Impact Analysis Summary

Components touched: `commands/utils.py` (`validate_sr_blocks`, `_lines_match` helper), `commands/utils.py` (new private helpers `_check_replace_syntax`, `_check_replace_imports`, `_check_replace_signature`, `_check_replace_regression`)
Workflows affected: `agent new-runbook` (via `run_generation_gates` → `validate_sr_blocks`), re-anchoring loop in `runbook_gates.py`
Risks identified: `ast.parse` on projected content may be slow for very large files — mitigated by 5MB size guard (skip silently if file exceeds limit)

## Test Strategy

- Unit — `_check_replace_syntax`: SQL at wrong indent → SyntaxError caught in projected output
- Unit — `_check_replace_syntax`: Valid replacement → no error
- Unit — `_check_replace_imports`: `from agent.core.implement.models import CodeBlock` (non-existent) → import error
- Unit — `_check_replace_imports`: `import os` (stdlib) → pass
- Unit — `_check_replace_signature`: `def foo(a, b)` replaced by `def foo(x)` → signature error
- Unit — `_check_replace_signature`: Same params, different body → pass
- Unit — `_check_replace_regression`: SEARCH 100 lines, REPLACE 10 lines → regression warning
- Unit — `_check_replace_regression`: REPLACE empty (intentional deletion) → no warning
- Unit — `_check_replace_regression`: Non-Python file below threshold → regression warning still fires
- Integration — `validate_sr_blocks` on INFRA-176 runbook content → returns mismatches for CodeBlock import and run_generation_gates stub
- Integration — `run_generation_gates` with REPLACE-side failures → correction_parts non-empty, re-anchoring does not suppress errors

## Rollback Plan

All four new checks are gated by private helper functions with isolated return values. To disable any check, set the corresponding `config` flag:
- `config.sr_check_syntax = False` — disables AC-1
- `config.sr_check_imports = False` — disables AC-2
- `config.sr_check_signatures = False` — disables AC-3
- `config.sr_stub_threshold = 0.0` — disables AC-4

No schema migrations or state changes required.

## Copyright

Copyright 2026 Justin Cook
