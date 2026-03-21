# INFRA-161: DoD Compliance Gate in `agent new-runbook`

## State

COMMITTED

## Problem Statement

`agent new-runbook` validates runbook structure, code syntax, and S/R block accuracy — but it does not verify that the generated runbook will actually satisfy the Definition of Done (DoD) enforced by `agent preflight`. The result is that AI-generated runbooks routinely pass all three current gates, then fail preflight on the first `agent implement` attempt because they omit common DoD requirements: missing tests, missing OTel instrumentation, missing CHANGELOG entries, missing license headers on new files, or incomplete AC coverage.

These 5 gaps account for the majority of post-implementation preflight failures. They are all catchable **at runbook generation time** — 4 of 5 by pure deterministic regex (zero AI cost), and 1 by a single secondary AI call.

This story introduces **Gate 4: DoD Compliance** — a composite verification pass embedded in the `new-runbook` generation loop that checks all 5 requirements before saving the runbook to disk.

## User Story

As a **Platform Developer**, I want `agent new-runbook` to verify that every generated runbook satisfies the full Definition of Done — including AC coverage, test steps, CHANGELOG entry, license headers, and OTel instrumentation — before saving the file, so that `agent implement` passes preflight on the first attempt the vast majority of the time.

## Acceptance Criteria

- [ ] **AC-1 — AC Coverage (4a)**: After schema + S/R gates pass, extract all `- [ ]` and `- [x]` Acceptance Criteria from the parent story. Make a secondary AI call with a structured prompt asking which ACs are not addressed by the runbook. If gaps are found, assemble a correction prompt and retry (consuming one slot from `max_attempts`). Helper functions: `extract_acs`, `build_ac_coverage_prompt`, `parse_ac_gaps` in `agent/commands/utils.py`.

- [ ] **AC-2 — Test Coverage (4b)**: For every `[NEW]` source file (non-boilerplate `.py`, `.ts`, `.go`, etc.) in the runbook, verify a corresponding paired test file step (`test_<module>.py` or `<module>_test.py`) exists as a `[NEW]` or `[MODIFY]` block. Files such as `__init__.py`, `conftest.py`, and non-source extensions are excluded. If any implementation file lacks a paired test step, include the specific file path in the correction prompt. Deterministic regex check — no AI call required.

- [ ] **AC-3 — CHANGELOG Entry (4c)**: Verify `CHANGELOG.md` appears as a modified or new file in the runbook. If absent, include `"CHANGELOG.md is not updated — add a [MODIFY] CHANGELOG.md step"` in the correction prompt. Deterministic check.

- [ ] **AC-4 — License Headers (4d)**: For every `[NEW] *.py` block in the runbook, verify the code content contains the Apache 2.0 preamble (`# Copyright` + `# Licensed under the Apache License`). For any `[NEW]` Python file missing the header, include the specific file path in the correction prompt. Deterministic check.

- [ ] **AC-5 — OTel Spans (4e)**: When the parent story content contains observability-related keywords (`opentelemetry`, `otel`, `tracing`, `span`, `observability`), verify that any `[NEW]` or `[MODIFY]` step targeting a file in `commands/` or `core/` includes at least one `tracer.start_as_current_span(` or `tracer.start` call. If the story does not mention observability, this check is skipped. Deterministic check.

- [ ] **AC-6 — Unified Correction Prompt**: All gaps from AC-1 through AC-5 are collected in a single pass and bundled into one combined correction prompt per retry iteration. The prompt explicitly lists each gap and instructs the AI to return the full corrected runbook. Only one retry slot is consumed per correction cycle regardless of how many gaps are found.

- [ ] **AC-7 — Retry Budget Shared**: The DoD gate uses the existing `max_attempts = 3` budget shared with gates 1–3. If DoD gaps persist after all retries, exit `1` and list the unresolved gaps. No runbook file is written.

- [ ] **AC-8 — Skip Gracefully When No Story**: If no parent story file is found on disk, skip ACs 1 (AC coverage check) silently. ACs 2–5 (deterministic checks) still run regardless of whether a story file exists.

- [ ] **AC-9 — Observability**: OTel span `dod_compliance_gate` with attributes `story_id`, `attempt`, `gap_count`, `gaps` (comma-joined list of gap IDs e.g. `"4a,4c,4d"`), `outcome` (`pass|retry|corrected|exhausted`). Structured log events: `dod_compliance_pass`, `dod_compliance_fail` (list of gaps), `dod_compliance_correction_attempt`, `dod_compliance_exhausted`.

- [ ] **AC-10 — Security**: Story content passed to the secondary AI call (AC-1) is scrubbed with `scrub_sensitive_data` before embedding in the prompt.

- [ ] **AC-11 — Tests**: Unit tests for each helper function (`extract_acs`, `build_ac_coverage_prompt`, `parse_ac_gaps`, `check_test_coverage`, `check_changelog_entry`, `check_license_headers`, `check_otel_spans`, `build_dod_correction_prompt`). Integration tests for the combined correction loop: all-pass, single gap, multiple gaps, exhausted retries, no-story skip.

## Non-Functional Requirements

- **Latency (happy path)**: < 1 second overhead — all deterministic checks (4b–4e) are pure Python, no I/O, no AI.
- **Latency (correction path)**: One additional AI round-trip only when gaps are found. AC coverage prompt is bounded by trimming the runbook to the Implementation Steps section.
- **Atomicity**: No runbook file is written until all 4 gates pass (schema → code → S/R → DoD compliance).
- **Security**: `scrub_sensitive_data` applied to story AC content and runbook content before any AI call.
- **Prompt efficiency**: All gaps (4a–4e) are bundled into a single correction prompt, not one prompt per gap.

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight
- ADR-022: Interactive Fixer Pattern
- ADR-040: Agentic Tool-Calling Loop Architecture
- ADR-041: Line of Code Standards

## Linked Journeys

- JRN-089: Generate Runbook with Targeted Codebase Introspection
- JRN-056: Full Implementation Workflow

## Impact Analysis Summary

**New / Modified files:**
- `agent/commands/dod_checks.py` — **[NEW]** DoD Compliance Gate helpers extracted from `utils.py` (INFRA-165 LOC quality refactor): `extract_acs`, `build_ac_coverage_prompt`, `parse_ac_gaps`, `check_test_coverage`, `check_changelog_entry`, `check_license_headers`, `check_otel_spans`, `build_dod_correction_prompt`, `auto_fix_license_headers`, `auto_fix_changelog_step`.
- `agent/commands/runbook_helpers.py` — **[NEW]** Runbook helpers extracted from `runbook.py` (INFRA-165 LOC quality refactor): `ComplexityMetrics`, `score_story_complexity`, `generate_decomposition_plan`, `load_journey_context`, `retrieve_dynamic_rules`, `parse_split_request`.
- `agent/commands/utils.py` — **[MODIFY]** DoD helpers moved to `dod_checks.py`; re-exported for backward compatibility.
- `agent/commands/runbook.py` — **[MODIFY]** Wire Gate 4 (`dod_compliance_gate` OTel span + deterministic checkers + correction-prompt retry loop). Complexity/helper functions moved to `runbook_helpers.py`; imported for backward compatibility.
- `agent/commands/tests/test_dod_compliance.py` — **[NEW]** Unit tests for all helper functions (16 unit tests).
- `agent/commands/tests/test_dod_compliance_integration.py` — **[NEW]** Integration tests for the gate composition (8 integration tests).
- `agent/commands/tests/test_dod_gate_orchestration.py` — **[NEW]** Orchestration-level integration tests for Gate 4 control flow (retry, corrected, exhausted, no-story skip — 11 tests).
- `CHANGELOG.md` — **[MODIFY]** Add INFRA-161 entry.
- `agent/core/implement/guards.py` — **[MODIFY]** Two prerequisite fixes: (1) missing trailing newlines auto-corrected with warning; (2) `check_imports` exempts test-only imports (`pytest`, `typer`, etc.) for `test_*.py` / `*_test.py`.

**Workflows affected:** `agent new-runbook` only. The `agent implement` pipeline is unchanged for non-test files.

**Risks:**
- False positives from the OTel check (4e) for stories that don't touch commands/core — mitigated by scoping to file paths matching `commands/` or `core/`.

## Test Strategy

**Unit — `extract_acs`**: Parse a story with open and closed ACs; assert all checkbox items returned; non-checkbox bullets excluded; missing section → `[]`.

**Unit — `build_ac_coverage_prompt`**: Assert prompt contains each AC label (`AC-1`, `AC-2`, ...) and closes with `ALL_PASS` or `AC-N:` format instruction.

**Unit — `parse_ac_gaps`**: `ALL_PASS` → `[]`; `AC-1: ...\nAC-3: ...` → `['AC-1', 'AC-3']`; empty → `[]`.

**Unit — `check_test_coverage`**: Runbook with `tests/test_foo.py` → passes; runbook with no test path → fails with descriptive message.

**Unit — `check_changelog_entry`**: Runbook with `CHANGELOG.md` in a `[MODIFY]` header → passes; missing → fails.

**Unit — `check_license_headers`**: `[NEW] foo.py` containing `# Copyright` + `Apache` → passes; missing header → fails with file path.

**Unit — `check_otel_spans`**: Runbook touching `commands/` file with `start_as_current_span` in content → passes; missing → fails.

**Unit — `build_dod_correction_prompt`**: Given a mixed list of deterministic + AC gaps, assert all gap descriptions appear in the prompt and the instruction to return the full runbook is present.

**Integration — all pass**: Mock AI (AC coverage returns `ALL_PASS`); all deterministic checks pass → gate exits cleanly, no retry.

**Integration — multiple gaps corrected**: Mock first AI response missing tests + CHANGELOG; second response includes both → gate exits after one retry, `dod_compliance_corrected` logged.

**Integration — exhausted retries**: AC gaps persist through all attempts → exit `1`, `dod_compliance_exhausted` logged, no file written.

**Integration — no story file**: Story path doesn't exist → AC-1 skipped, deterministic checks 4b–4e still run (pass), gate succeeds.

## Rollback Plan

Remove the `dod_compliance_gate` block from `runbook.py` and the Gate 4 helpers from `dod_checks.py` (previously in `utils.py`). The pipeline reverts to the three-gate behaviour. No data migration required.

## Copyright

Copyright 2026 Justin Cook
