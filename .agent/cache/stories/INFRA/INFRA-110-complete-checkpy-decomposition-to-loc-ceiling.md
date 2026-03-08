# INFRA-110: Complete check.py decomposition to LOC ceiling

## State

DRAFT

## Problem Statement

The `commands/check.py` module currently stands at 1,597 LOC, significantly exceeding the 500 LOC maintainability ceiling defined in ADR-041. INFRA-103 delivered the first slice (extracted `core/check/system.py` and `core/check/quality.py`), and also fixed Vertex AI ADC project auto-detection and ADK diff truncation limits. This story completes the remaining extraction work, reducing the facade to ≤500 LOC.

## User Story

As a **Platform Engineer**, I want to **complete the decomposition of `commands/check.py`** so that **the facade is a thin Typer router, each concern lives in its own module, and the codebase fully complies with ADR-041.**

## Parent Plan

INFRA-099

## Acceptance Criteria

- [ ] **AC-1 (Decomposition)**: AI Governance Council call-sites and preflight/PR orchestration logic extracted from `commands/check.py` into `core/check/` sub-modules. Facade reduced to a thin Typer router ≤500 LOC.
- [ ] **AC-2 (Type Safety)**: Any remaining `dict` return types in `core/check/` tightened to `TypedDict` definitions (following `LinkedJourneysResult` / `JourneyCoverageResult` pattern already shipped in INFRA-103).
- [ ] **AC-3 (Tests)**: All existing `tests/commands/test_check.py` tests pass without modification after move. New unit tests cover extracted modules.
- [x] **AC-4 (ADC Fallback)** *(done — INFRA-103)*: Vertex AI auto-detects `GOOGLE_CLOUD_PROJECT` via `google.auth.default()` when env var is absent.
- [x] **AC-5 (Diff Truncation)** *(done — INFRA-103)*: ADK orchestrator applies provider-aware limits (vertex/gemini=200k, gh=6k, default=40k). Provider resolved post `_ensure_initialized()` so name is never empty.
- [x] **AC-6 (Provider Fallback Warning)** *(done — INFRA-103)*: Neutral warning when configured provider is not in active client pool.
- [x] **AC-7 (Implement Gate as Warning)** *(done — INFRA-103)*: `agent implement` post-apply gate failures produce a `⚠️` warning and set story state to `REVIEW_NEEDED` instead of blocking the run. `preflight` remains the hard gatekeeper. Tests in `tests/core/check/test_implement_gate.py`.
- [x] **AC-8 (Governance Determinism — temperature)** *(done — INFRA-103)*: ADK governance adapter passes `temperature=0.0` on all LLM calls, matching the native path's gatekeeper-mode behaviour. Both paths now converge on a deterministic response.
- [x] **AC-9 (Governance Determinism — previous verdicts)** *(done — INFRA-103)*: Per-role verdicts written to `.preflight_result` (PASS and BLOCK runs). Next run reads them and injects a `<previous_verdicts>` block into every agent's prompt, preventing oscillation on resolved findings.
- [x] **AC-10 (Governance Determinism — scope lock)** *(done — INFRA-103)*: `SCOPE RULES` added to all governance agent system prompts: cite sources or pass, acknowledge documented co-commits, don't contradict previous verdicts.
- [x] **AC-11 (validate_story TypedDict)** *(done — INFRA-103)*: `core/check/system.validate_story` now returns `ValidateStoryResult` TypedDict; rich/typer logic moved to a thin `commands/check.validate_story` CLI wrapper — decoupling core from presentation per ADR-041.
- [ ] **AC-12 (preflight() decomposition)**: The `preflight()` function in `commands/check.py` is currently ~1 000 LOC. It must be decomposed: governance orchestration, report formatting, and credential checks extracted to `core/check/` sub-modules. `preflight()` facade must reach ≤500 LOC.

## Non-Functional Requirements

- **Performance**: No latency increase in command execution or preflight flow.
- **Compliance**: ADR-041 500 LOC ceiling per module.
- **Observability**: Logging captures active project ID and truncation limits applied.

## Linked ADRs

- ADR-041: Module size limits.

## Linked Journeys

- JRN-036: Preflight Governance Check
- JRN-072: Terminal Console TUI Chat

## Impact Analysis Summary

- **Components touched**: `commands/check.py`, `core/check/` (new sub-modules for governance/preflight extraction).
- **Workflows affected**: `agent preflight`, `agent pr`, AI Governance Council call-sites.
- **Risks identified**: Regression in preflight call flow. Mitigate with full `tests/commands/test_check.py` pass before merge.

## Test Strategy

- **Unit Tests**: `pytest tests/core/check/` covering extracted modules independently.
- **Regression**: `tests/commands/test_check.py` suite passes without modification.
- **Integration**: `agent preflight --story INFRA-110` end-to-end after decomposition.

## Rollback Plan

- Revert to INFRA-103 state via `git revert`. No data migrations required.

## Copyright

Copyright 2026 Justin Cook
