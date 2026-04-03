# INFRA-159: Validate S/R Search Blocks Against Actual File Content at Runbook Generation Time

## State

COMMITTED

## Problem Statement

`agent new-runbook` generates implementation runbooks containing `<<<SEARCH/===/>>>REPLACE` blocks. The AI frequently halluccinates the content of the `<<<SEARCH` section — writing lines that don't exist verbatim in the target file. This passes undetected through the runbook generation pipeline and is only discovered when `agent implement --apply` attempts to match the block and fails.

INFRA-156 (AC-6) will make that failure loud (hard exit rather than silent skip), but the developer is still stuck at that point with a runbook containing invalid search content that must be manually corrected before implementation can proceed.

The fix is to validate S/R blocks **at generation time** — before the runbook is written to disk. After the AI panel produces a runbook draft, each `<<<SEARCH` block targeting an existing file must be verified against the actual file content. If any block fails to match, the AI is re-prompted with the real file content and asked to correct the search target — up to a configurable number of retries. Only a fully-verified runbook is saved.

## User Story

As a **Platform Developer**, I want **`agent new-runbook` to verify that every `<<<SEARCH` block matches the actual target file before saving the runbook** so that **`agent implement` never encounters a search-mismatch error caused by hallucinated file content.**

## Acceptance Criteria

- [ ] **AC-1 — Post-generation S/R validation pass**: After the AI panel returns a runbook draft, `new-runbook` extracts all `[MODIFY]` blocks with `<<<SEARCH/===/>>>REPLACE` syntax and checks each SEARCH section against the actual target file on disk.

- [ ] **AC-2 — Hard block on mismatch**: If any SEARCH block does not match the target file verbatim, the runbook is **not written to disk**. The mismatching blocks are collected and passed back to the AI in a correction prompt.

- [ ] **AC-3 — Correction prompt**: The correction prompt includes: (a) the full content of the target file, (b) the failing SEARCH block, and (c) an instruction to rewrite the block with a search string that exactly matches the file. The corrected runbook replaces the draft.

- [ ] **AC-4 — Retry limit**: The correction loop retries up to **2 times** (consistent with the code-gate self-healing loop in INFRA-155). If all retries are exhausted with remaining mismatches, the command exits `1` with a message listing the unresolvable blocks, prompting the developer to check the target file manually.

- [ ] **AC-5 — Skip for new files**: `[NEW]` blocks (creating files that do not yet exist on disk) are exempt from validation — there is no existing content to match against.

- [ ] **AC-6 — Skip for non-existent target files referenced in MODIFY blocks**: If a `[MODIFY]` block references a file that does not exist, it is treated as a validation error immediately (no retry) — the developer is informed that the target file is missing.

- [ ] **AC-7 — Observability**: Structured log events emitted: `sr_validation_pass` (all blocks matched), `sr_validation_fail` (mismatch count, file, block index), `sr_correction_attempt` (attempt number), `sr_correction_success`, `sr_correction_exhausted`.

- [ ] **Negative Test — All blocks valid**: Given a runbook where all SEARCH blocks match their target files, the runbook is saved without any correction loop.

- [ ] **Negative Test — Unresolvable after retries**: Given a runbook where a SEARCH block cannot be corrected after 2 retries, the command exits `1`, no runbook file is written, and the error output identifies the file and block.

- [ ] **Negative Test — Target file missing**: Given a `[MODIFY]` block targeting a non-existent file, the command exits `1` with an appropriate message without entering the correction loop.

## Non-Functional Requirements

- **Performance**: The validation pass is pure local string matching — must complete in < 100 ms per block. AI correction calls are bounded by the 2-retry limit.
- **Atomicity**: The runbook file is written only after all blocks pass validation (or written with a `_UNVERIFIED` suffix if the user passes `--force`).
- **Observability**: All events use the project's structured logging pattern (`logger.info(..., extra={...})`).
- **Security**: No file contents are logged at INFO level or above.

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight
- ADR-022: Interactive Fixer Pattern
- ADR-040: Agentic Tool-Calling Loop Architecture

## Linked Journeys

- JRN-089: Generate Runbook with Targeted Codebase Introspection
- JRN-056: Full Implementation Workflow

## Impact Analysis Summary

**Components touched:**
- `agent/core/implement/sr_validation.py` — **[MODIFY]** add `_dedent_normalize_match` helper and wire it as Layer 1.5 inside `validate_and_correct_sr_blocks`, between the exact-match check and the fuzzy/AI re-anchor path. This module is the shared S/R validation engine already invoked by `agent new-runbook` at generation time (via `runbook.py`) and also at apply time (via `guards.py`). The logic correctly lives here rather than in `commands/utils.py` to avoid duplication.
- `CHANGELOG.md` — **[MODIFY]** add INFRA-159 entry under Unreleased

**Workflows affected:** `agent new-runbook` — indentation-shift mismatches (e.g. AI omitting class-level indentation on method SEARCH blocks) are now auto-corrected without an AI call, before falling through to fuzzy matching or AI re-anchoring.

**Risks identified:**
- `_dedent_normalize_match` requires a 100% content match after stripping per-line leading whitespace. Over-correction is not possible — if the dedented strings don't match exactly, the layer is a no-op.
- Correction re-prompting adds latency (one extra AI call per retry) — bounded by the 2-retry limit.
- Stringent verbatim matching may reject valid blocks where the AI uses equivalent whitespace — the match should normalise trailing whitespace per line but require exact content otherwise.

**Co-committed housekeeping (out-of-scope but bundled):**
- `agent/tests/commands/test_create_tool.py` — **[MODIFY]** fixed `test_security_scan_allows_override` cleanup to use `_get_custom_tools_dir()` for the absolute output path (was using a wrong relative path, leaving `test_override.py` on disk after the test run); removed duplicate copyright header
- `agent/tests/journeys/test_jrn_001.py` — **[MODIFY]** skip gracefully when running on the `main` branch where no feature story is present (prevents false failures from interactive prompt abort)
- `agent/tests/journeys/test_jrn_002.py` — **[MODIFY]** accept `"Aborted"` as a valid graceful-failure outcome when running on `main` branch without a feature story

## Test Strategy

- **Unit — `validate_sr_blocks` (all match)**: Given a mock runbook and mock file contents where all SEARCH blocks are present, assert `[]` (no mismatches) is returned.
- **Unit — `validate_sr_blocks` (one mismatch)**: Given one SEARCH block whose content is not in the target file, assert the mismatch is returned with the correct file and block index.
- **Unit — new file exempt**: Given a `[NEW]` block, assert it is not validated.
- **Unit — `_dedent_normalize_match` (successful match)**: Given a SEARCH block where the first line is missing its class-level 4-space indent (the exact AI hallucination pattern), assert the function returns the correctly-indented region from the actual file content verbatim.
- **Unit — `_dedent_normalize_match` (no match)**: Given a SEARCH block whose content genuinely does not exist in the file even after stripping indentation, assert the function returns `None`.
- **Integration — indentation error corrected without AI call**: Run `validate_and_correct_sr_blocks` with a runbook containing an indentation-shifted SEARCH block; assert the corrected runbook contains the properly-indented anchor and that no AI service call was made.
- **Integration — correction loop (success)**: Mock AI to return a bad runbook on first call and a corrected runbook on second call; assert the saved runbook contains the corrected block.
- **Integration — correction loop (exhausted)**: Mock AI to always return bad SEARCH content; assert exit code `1` and no runbook file written after 2 retries.
- **Negative test — missing target file**: Assert exit `1` and error message when a `[MODIFY]` block targets a non-existent path.

## Rollback Plan

Remove the `validate_sr_blocks` call from `runbook.py` and the helper from `utils.py`. The runbook generation pipeline returns to its pre-INFRA-159 behaviour (no S/R pre-validation). INFRA-156 AC-6 remains in place as the last line of defence.

## Copyright

Copyright 2026 Justin Cook
