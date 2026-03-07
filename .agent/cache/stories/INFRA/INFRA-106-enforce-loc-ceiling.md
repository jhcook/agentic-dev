# INFRA-106: Enforce LOC Ceiling via CI and Documentation

## State

DRAFT

## Parent Plan

INFRA-099

## Problem Statement

The structural decomposition delivered by INFRA-100 through INFRA-105 eliminates the current monolithic files, but without automated enforcement the 500 LOC ceiling defined in ADR-041 will erode over time. There is no CI gate, no pre-commit hook, and no import hygiene check preventing files from growing past the ceiling again. This story closes that gap.

## User Story

As a **Platform Engineer**, I want to **enforce the 500 LOC ceiling and import hygiene rules automatically in CI and pre-commit** so that **no future PR can silently re-introduce a God Object and all module decomposition standards are self-sustaining.**

## Acceptance Criteria

- [ ] **AC-1**: A script `scripts/check_loc.py` reports all Python files under `.agent/src/agent/` that exceed 500 LOC, exits non-zero if any are found, and prints a clear violation message with file path and line count.
- [ ] **AC-2**: A script `scripts/check_imports.py` (or integration into `check_loc.py`) reports all inter-package circular imports, using `importlib` or static AST analysis, and exits non-zero on failure.
- [ ] **AC-3**: Both scripts are wired into the `agent preflight` pipeline as a new `LOC Ceiling` gate in `commands/check.py` (routed through `core/check/quality.py` post INFRA-103).
- [ ] **AC-4**: A `.pre-commit-config.yaml` hook entry (or equivalent `agent` hook) runs `check_loc.py` on staged Python files before commit.
- [ ] **AC-5**: `README.md` and `CHANGELOG.md` are updated to document the LOC ceiling, the enforcement mechanism, and the ADR-041 reference.
- [ ] **AC-6**: `docs/adr/ADR-041-module-decomposition.md` is created (or updated) with the rationale, the 500 LOC ceiling rule, the enforcement mechanism, and the approved exceptions process.
- [ ] **AC-7**: Unit tests in `tests/scripts/test_check_loc.py` verify the script correctly identifies violating files and exits cleanly on a compliant codebase.
- [ ] **Negative Test**: `check_loc.py` handles binary files, empty files, and non-Python files gracefully without crashing.

## Non-Functional Requirements

- **Performance**: LOC check script completes in under 5 seconds on the full `.agent/src/` tree.
- **Security**: Scripts must not execute arbitrary code from the files they analyse (AST/line-count only).
- **Compliance**: N/A.
- **Observability**: `check_loc.py` logs a structured summary (file, LOC, pass/fail) to stdout suitable for CI log capture.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-036: Preflight Governance Check

## Impact Analysis Summary

- **Components touched**: `scripts/check_loc.py` (new), `scripts/check_imports.py` (new), `commands/check.py` or `core/check/quality.py` (gate wiring), `.pre-commit-config.yaml` (hook entry), `README.md`, `CHANGELOG.md`, `docs/adr/ADR-041-module-decomposition.md`.
- **Workflows affected**: `agent preflight`, pre-commit hook pipeline.
- **Risks identified**: Must run **after** INFRA-100–105 are merged so the baseline codebase is already compliant; running against the pre-decomposition tree would produce false positive violations.

## Test Strategy

- **Unit Testing**: Synthetic test fixtures with compliant and non-compliant Python files to validate exit codes and output format.
- **Integration**: Run `agent preflight` on the post-decomposition codebase and confirm the `LOC Ceiling` gate passes with zero violations.
- **Regression**: Ensure existing gates in `preflight` are unaffected by the new gate addition.

## Rollback Plan

- Remove `scripts/check_loc.py` and `scripts/check_imports.py`.
- Revert the gate wiring in `core/check/quality.py` and the `.pre-commit-config.yaml` entry.
- Revert `CHANGELOG.md` and `README.md` edits.

## Copyright

Copyright 2026 Justin Cook
