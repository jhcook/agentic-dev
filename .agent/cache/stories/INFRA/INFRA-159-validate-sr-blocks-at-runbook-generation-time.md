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
- `agent/commands/runbook.py` — **[MODIFY]** import `validate_sr_blocks` and `generate_sr_correction_prompt`; replace TODO stub with full self-healing S/R validation loop (AC-1, AC-2, AC-4, AC-6, AC-7)
- `agent/commands/utils.py` — **[MODIFY]** add `_lines_match`, `validate_sr_blocks`, and `generate_sr_correction_prompt` helpers; add `List` import and `scrub_sensitive_data` import from `agent.core.utils`
- `CHANGELOG.md` — **[MODIFY]** add INFRA-159 S/R pre-validation entry under Unreleased

**Workflows affected:** `agent new-runbook` — S/R validation gate inserted between AI generation and file save. When mismatches are found, a self-healing re-prompt is issued up to `max_attempts - 1` times before hard failure.

**Risks identified:**
- Correction re-prompting adds latency (one extra AI call per retry) — bounded by the 2-retry limit.
- Stringent verbatim matching may reject valid blocks where the AI uses equivalent whitespace — the match should normalise trailing whitespace per line but require exact content otherwise.

## Test Strategy

- **Unit — `validate_sr_blocks` (all match)**: Given a mock runbook and mock file contents where all SEARCH blocks are present, assert `[]` (no mismatches) is returned.
- **Unit — `validate_sr_blocks` (one mismatch)**: Given one SEARCH block whose content is not in the target file, assert the mismatch is returned with the correct file and block index.
- **Unit — new file exempt**: Given a `[NEW]` block, assert it is not validated.
- **Integration — correction loop (success)**: Mock AI to return a bad runbook on first call and a corrected runbook on second call; assert the saved runbook contains the corrected block.
- **Integration — correction loop (exhausted)**: Mock AI to always return bad SEARCH content; assert exit code `1` and no runbook file written after 2 retries.
- **Negative test — missing target file**: Assert exit `1` and error message when a `[MODIFY]` block targets a non-existent path.

## Rollback Plan

Remove the `validate_sr_blocks` call from `runbook.py` and the helper from `utils.py`. The runbook generation pipeline returns to its pre-INFRA-159 behaviour (no S/R pre-validation). INFRA-156 AC-6 remains in place as the last line of defence.

## Copyright

Copyright 2026 Justin Cook
