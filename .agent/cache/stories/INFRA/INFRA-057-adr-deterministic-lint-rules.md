# INFRA-057: ADR-Driven Deterministic Lint Rules

## State

IN_PROGRESS

## Problem Statement

ADRs define architectural constraints (e.g., lazy initialization, import boundaries, breaking change definitions), but enforcement is purely advisory — the governance panel *interprets* ADRs via LLM prompts. This means the same ADR can produce inconsistent verdicts across runs, and violations slip through when the panel misses context. ADRs that encode verifiable rules should generate deterministic, repeatable lint checks that always pass or fail the same way.

## User Story

As a **developer governed by the agent framework**, I want ADR-defined constraints to be enforced by automated lint rules so that architectural regressions are caught deterministically without relying on AI interpretation.

## Acceptance Criteria

- [ ] **AC-1**: ADRs declare enforcement rules in fenced `enforcement` YAML blocks (inline in the ADR markdown). Schema: `type` (lint), `pattern` (regex), `scope` (file glob), `violation_message`. Enforcement blocks are only extracted from ADRs in `ACCEPTED` state — `DRAFT` and `SUPERSEDED` ADRs are skipped.
- [ ] **AC-2**: `agent check lint` reads enforcement blocks from all active ADRs via a robust fenced-block parser and runs the declared patterns against matching files. A new `run_adr_enforcement()` function follows the existing `run_linter` dispatcher pattern in `lint.py`.
- [ ] **AC-3**: ADR-025 (Lazy Init) has an enforcement block that flags module-level `ai_service` imports and `AIService()` instantiation in `commands/`. Uses an indentation heuristic (pattern matches only at column 0) to distinguish module-level from in-function imports.
- [ ] **AC-4**: Architectural boundary ADR has enforcement blocks that flag cross-boundary imports (e.g., mobile importing backend modules, web importing backend modules).
- [ ] **AC-5**: `agent preflight` includes ADR lint checks as a deterministic gate before the AI panel review. Preflight output shows a separate "ADR Lint" section distinct from "Code Lint (ruff)".
- [ ] **AC-6**: Lint violations produce structured output in ruff/eslint convention: `file:line:col: ADR-XXX message`. Support `--json` flag for machine-parseable output.
- [ ] **AC-7**: Enforcement respects `EXC-*` exception records (ADR-021) — suppressed violations are skipped with a note in verbose output.
- [ ] **AC-8**: Regex patterns are executed with a 5-second timeout per pattern per file to prevent ReDoS from badly authored patterns. Timeout produces a config error, not a crash.
- [ ] **AC-9**: Enforcement scope globs are constrained to the project root. A scope of `"/"` or absolute paths is rejected during parsing.
- [ ] **AC-10**: `agent check lint --adr-only` flag runs only ADR enforcement, skipping ruff/eslint/markdownlint.
- [ ] **Negative Test**: An ADR with `status: SUPERSEDED` does not generate lint checks.
- [ ] **Negative Test**: An ADR in `DRAFT` state does not generate lint checks.
- [ ] **Negative Test**: An ADR with an invalid regex pattern produces a config error for that ADR, does not crash the lint run.

## Non-Functional Requirements

- Performance: Lint checks complete in < 5s for a typical changeset.
- Extensibility: Enforcement schema supports future types (e.g., `type: ast`, `type: test_required`) without schema changes.
- Compliance: Deterministic checks provide SOC 2 CC7.1 audit evidence independent of AI availability. Results are persisted for `agent audit` reporting.
- Observability: ADR lint results captured in OpenTelemetry spans consistent with existing `run_linter` tracing.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-021 (Architectural Exception Records)
- ADR-025 (Lazy Initialization)

## Linked Journeys

- JRN-036 (Interactive Preflight Repair)
- JRN-052 (ADR Lint Enforcement)

## Panel Advice Applied

- **@architect**: Enforcement blocks live inline in ADR markdown (fenced YAML). Follow `run_linter` dispatcher pattern. (→ AC-1, AC-2)
- **@backend**: ADR-025 regex uses indentation heuristic for module-level detection. (→ AC-3)
- **@security**: 5s regex timeout via `signal.alarm`. Scope constrained to project root. (→ AC-8, AC-9)
- **@product**: Output matches ruff/eslint convention. Separate "ADR Lint" section in preflight. (→ AC-5, AC-6)
- **@qa**: Test DRAFT/SUPERSEDED status filtering. Test invalid regex graceful failure. (→ AC-1, Negative Tests)
- **@docs**: ADR-025 updated with enforcement block as canonical example. `--adr-only` flag for targeted runs. (→ AC-10)
- **@compliance**: Results persisted for `agent audit`. EXC-* integration. (→ AC-7, NFRs)
- **@observability**: OpenTelemetry spans for ADR lint. JSON output option. (→ AC-6, NFRs)

## Impact Analysis Summary

Components touched:

- `.agent/adrs/ADR-025-lazy-ai-service-initialization.md` — add `enforcement` block (canonical example)
- `.agent/src/agent/commands/lint.py` — new `run_adr_enforcement()` function, `--adr-only` flag
- `.agent/src/agent/commands/check.py` — integrate ADR lint as separate preflight section

Workflows affected:

- `/preflight` — new deterministic gate before AI panel
- `agent check lint` — new ADR enforcement source

Risks identified:

- Over-constraining: Overly strict patterns could produce false positives. Mitigated by EXC-* exception records (INFRA-056) and indentation heuristics.
- ReDoS: Developer-authored regex could hang execution. Mitigated by 5s timeout per pattern.
- Module-level detection limits: Indentation heuristic covers 95% of Python cases; future `type: ast` enforcement handles the rest.

## Test Strategy

- **Unit — Parser**: Enforcement block extraction from ADR markdown (valid, malformed, missing, multiple blocks).
- **Unit — Regex**: Pattern matching with indentation heuristic against sample files.
- **Unit — Timeout**: Regex timeout triggers config error, not crash.
- **Unit — Scope**: Absolute path / root scope rejected. Glob matching uses `pathlib.Path.glob()`.
- **Unit — EXC integration**: Exception record suppresses matching violation.
- **Integration — ADR-025**: Create temp file with real ADR-025 violation (`ai_service = AIService()` at module scope in `commands/`), run `agent check lint`, assert structured output with ADR reference, file, line. Remove violation, re-run, assert clean pass.
- **Integration — Status filtering**: ADR in SUPERSEDED/DRAFT state produces no enforcement.
- **Integration — Preflight**: `agent preflight` runs ADR lint before panel, separate output section.

## Rollback Plan

- Remove `enforcement` blocks from ADRs (additive content, safe to remove).
- Revert lint.py and check.py changes.
- Preflight falls back to AI-only governance.
