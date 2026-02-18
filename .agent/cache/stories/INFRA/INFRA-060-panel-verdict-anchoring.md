# INFRA-060: Panel Verdict Anchoring

## State

COMMITTED

## Problem Statement

The governance panel produces verdicts (PASS/BLOCK) but there is no requirement that the review references the specific ADRs or journeys relevant to the changeset. This means:

1. The panel can PASS a change that violates an ADR it didn't consider.
2. Reviews are inconsistent — the same change may reference different ADRs on different runs.
3. There is no post-hoc auditability of *which governance artifacts informed the verdict*.

The panel is advisory, but its advice should be anchored to the project's first-class governance objects.

## User Story

As a **developer governed by the agent framework**, I want the governance panel to explicitly cite the ADRs and journeys it considered so that I can trust the review is comprehensive and auditable.

## Acceptance Criteria

- [ ] **AC-1**: The system prompt (line ~399 in `governance.py`) is updated to require a `REFERENCES:` section in the structured output format: `REFERENCES:\n- ADR-NNN: <reason>\n- JRN-NNN: <reason>`.
- [ ] **AC-2**: A compact one-line list of available ADR/JRN/EXC IDs is injected into each role's prompt context: `AVAILABLE REFERENCES: ADR-001, ADR-002, ..., JRN-001, ...`. IDs only — `_load_adrs()` already injects full summaries via `<adrs>` tag.
- [ ] **AC-3**: `_parse_findings()` is extended to extract a `references` field using regex `\b(ADR-\d+|JRN-\d+|EXC-\d+)\b` across the full AI output (not just the REFERENCES section). Dual strategy: parse formal `REFERENCES:` section if present, AND scan full text as fallback.
- [ ] **AC-4**: `_validate_references(refs)` checks the filesystem: `.agent/adrs/` for ADR and EXC files, `.agent/cache/journeys/` for JRN files. Returns `(valid_refs, invalid_refs)`.
- [ ] **AC-5**: Per-role JSON report includes `references: {cited: [], valid: [], invalid: []}`.
- [ ] **AC-6**: If the panel omits a relevant ADR/journey (based on INFRA-059's impact map), preflight emits a warning: "Panel did not consider ADR-XXX (relevant to changed files)". Graceful degradation: if INFRA-059's journey impact map is unavailable, skip this check with `ℹ️ Journey impact map not available — skipping completeness check`.
- [ ] **AC-7**: If the panel cites a non-existent ADR/JRN, preflight emits: "⚠️ @{role} cited ADR-099 which does not exist".
- [ ] **AC-8**: If a role provides no references at all, preflight emits: "⚠️ @{role} — no references provided".
- [ ] **AC-9**: The audit log (`governance-{story_id}-{timestamp}.md`) includes a `## Reference Validation` section (appended before write at line ~487) with full `valid_refs` and `invalid_refs` lists, not just counts. Traceability chain: `Code Change → Diff → AI Review → Citation → Validation`.
- [ ] **AC-10**: OpenTelemetry span attributes: per-role `role_name`, `ref_count`, `valid_count`, `invalid_count`. Aggregate: `panel.total_refs`, `panel.citation_rate` (roles_with_refs / total_roles), `panel.hallucination_rate` (invalid_refs / total_refs).
- [ ] **AC-11** *(Panel)*: Reference extraction runs on **both** parsed (gatekeeper mode) and raw (consultative mode) output. In consultative mode (line ~417-418), `_parse_findings()` is not called — `_extract_references()` must run separately on raw AI output.
- [ ] **AC-12** *(Panel)*: `_validate_references()` handles `EXC-\d+` patterns in the same `adrs_dir` as ADRs.
- [ ] **AC-13** *(Panel)*: Per-role references are deduplicated across multi-chunk reviews (same role reviewing multiple diff chunks).
- [ ] **AC-14** *(Panel)*: If a cited ADR has state `SUPERSEDED`, emit an info note: "ADR-XXX is SUPERSEDED — consider citing its replacement".
- [ ] **AC-15** *(Panel)*: `_parse_findings()` remains backward-compatible when `REFERENCES:` section is absent. Default: empty list.
- [ ] **AC-16** *(Panel)*: A Reference Summary Table is displayed after all role panels: `Reference | Status | Cited By`.
- [ ] **Negative Test**: A changeset touching no ADR-governed files does not require ADR citations.
- [ ] **Negative Test**: A missing or invalid reference produces a WARNING, not a BLOCK.

## Non-Functional Requirements

- **Auditability**: Panel references persisted in audit log for SOC 2 evidence. Full traceability chain: `Code Change → Diff → AI Review → Citation → Validation`. Audit log `## Reference Validation` section includes full lists, not just counts.
- **Non-blocking**: Missing/invalid references warn but don't block — deterministic lint checks (INFRA-057) handle hard enforcement.
- **Prompt Engineering**: Inject only IDs (one compact line), NOT full ADR content — `_load_adrs()` already injects summaries. Build the ID list inside `convene_council_full()` by extracting IDs from `adrs_content` (regex `ADR-\d+`) + scanning `config.journeys_dir` for JRN IDs.
- **Security**: Reference list derived from filesystem directory listings (`config.adrs_dir.glob()`, `config.journeys_dir.rglob()`), not user input. ADR-\d+ regex constrains glob patterns — no path traversal risk.
- **Backward Compatibility**: `_parse_findings()` works unchanged when `REFERENCES:` section is absent. New functions (`_extract_references()`, `_validate_references()`) are additive.
- **Module Placement**: `_extract_references()` and `_validate_references()` belong in `governance.py` alongside `_parse_findings()` — tightly coupled to prompt parsing.
- **Observability**: Citation rate tracked over time as prompt quality metric. Declining rate triggers prompt engineering review.

## Panel Advice Applied

- **@Architect**: Build `AVAILABLE REFERENCES:` line inside `convene_council_full()` (centralized, not in callers). Extract ADR IDs from `adrs_content` + scan `config.journeys_dir`. Function signature stays the same.
- **@QA**: Consultative mode gap identified — `_parse_findings()` never called in `mode == "consultative"` (line ~417-418). `_extract_references()` must run separately on raw output. Added AC-11. Multi-chunk dedup (AC-13). SUPERSEDED ADR info notes (AC-14). Tests for consultative mode and SUPERSEDED ADRs.
- **@Security**: Hallucination detection via validation — catches AI-fabricated ADR IDs. Filesystem-derived reference list — no prompt injection risk. ADR-\d+ regex constrains glob patterns.
- **@Product**: Non-blocking warnings correct for adoption. Reference Summary Table (AC-16) after all role panels. INFRA-059 graceful degradation (AC-6 updated).
- **@Observability**: Per-role span attributes (`role_name`, `ref_count`, `valid_count`, `invalid_count`). Aggregate metrics after role loop. Citation rate as prompt-quality adoption metric.
- **@Compliance**: Audit log `## Reference Validation` section appended before file write. Full `valid_refs`/`invalid_refs` lists. Traceability chain in section header.
- **@Backend**: Dual extraction strategy — parse `REFERENCES:` section if present, AND scan full text with regex as fallback. `_validate_references()` handles EXC- patterns in same `adrs_dir`. Verify `config.journeys_dir` exists.
- **@Docs**: CHANGELOG entry for reference validation. Prompt format documentation update.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-021 (Architectural Exception Records)

## Linked Journeys

- JRN-045 (Governance Hardening — Exception Records)

## Impact Analysis Summary

Components touched:

- `.agent/src/agent/core/governance.py` — update system prompt (line ~399), extend `_parse_findings` with `references` field, add `_extract_references()` and `_validate_references()`, inject compact ID list via `convene_council_full()`, consultative mode reference extraction path
- `.agent/src/agent/commands/check.py` — add Reference Summary Table after role panels, per-role reference display, SUPERSEDED ADR info notes
- `.agent/src/agent/core/context.py` — no changes (existing `_load_adrs()` already provides summaries; new ID-only line is separate)
- `.agent/src/agent/core/config.py` — verify `journeys_dir` attribute exists (add if missing: `config.agent_dir / "cache" / "journeys"`)

Workflows affected:

- `/preflight` — panel review now includes reference checking + validation summary
- `/panel` — updated prompt format with REFERENCES requirement, consultative mode extracts references from raw output

Risks identified:

- Prompt bloat: Mitigated by injecting only IDs (one compact line), not full ADR content.
- AI ignoring REFERENCES instruction: Treated as warning, monitored via citation rate metric.
- Reference format drift across providers: Regex handles variations (`ADR-025` vs `ADR 025`).
- INFRA-059 dependency: AC-6 completeness check gracefully degrades if journey impact map unavailable.

## Test Strategy

- Unit: `test_parse_findings_with_references()` — AI output with REFERENCES section parsed correctly.
- Unit: `test_parse_findings_no_references()` — backward-compatible, returns empty list.
- Unit: `test_extract_references()` — regex extracts ADR-025, JRN-012, EXC-001 from mixed text.
- Unit: `test_extract_references_dedup()` — same ADR cited 3x returns single entry.
- Unit: `test_validate_references_valid()` — ADR-025 exists on disk → valid.
- Unit: `test_validate_references_invalid()` — ADR-099 doesn't exist → invalid.
- Unit: `test_validate_references_exc()` — EXC-001 exists in `adrs_dir` → valid.
- Unit: `test_validate_references_mixed()` — mix of valid and invalid.
- Unit: `test_malformed_reference_ignored()` — `ADR25` (no hyphen) not extracted.
- Unit: `test_consultative_mode_reference_extraction()` — raw AI output (not parsed by `_parse_findings`) still yields references via `_extract_references()`.
- Unit: `test_superseded_adr_reference()` — citing SUPERSEDED ADR produces info note.
- Unit: `test_no_references_section_backward_compat()` — `_parse_findings()` without REFERENCES section returns default empty references.
- Integration: `agent panel INFRA-060 --ai` includes per-role references and Reference Summary Table.
- Integration: preflight with ADR-governed changeset emits warning if panel omits citation.
- Negative: changeset touching no ADR-governed files — no citation warnings.
- Negative: missing/invalid reference → WARNING, never BLOCK.

## Rollback Plan

- Remove `_extract_references()`, `_validate_references()` from `governance.py`.
- Revert prompt template changes (remove REFERENCES requirement and AVAILABLE REFERENCES line).
- Remove Reference Summary Table from `check.py`.
- Panel returns to unanchored verdicts (no regression in functionality — all new features are additive).
