# INFRA-102: Decompose Implement Command

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `commands/implement.py` module has grown to 1,819 LOC and conflates three orthogonal responsibilities: CLI surface (Typer command definitions and argument parsing), orchestration logic (step execution, file application, retry coordination), and circuit breaker enforcement (LOC tracking, warning thresholds, follow-up story generation). This makes it difficult to unit-test individual concerns in isolation and adds high cognitive overhead when modifying any single behaviour.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic implement command into a thin CLI facade and focused core modules** so that **the orchestration and circuit breaker logic can be independently tested, the 500 LOC ceiling is respected, and future step-level changes don't risk breaking the circuit breaker.**

## Acceptance Criteria

- [ ] **AC-1**: `commands/implement.py` is reduced to a thin Typer CLI facade ≤500 LOC that parses arguments and delegates to `core/implement/orchestrator.py`.
- [ ] **AC-2**: `core/implement/orchestrator.py` contains the step execution loop, `parse_code_blocks`, `apply_code_blocks`, safe-apply guards (INFRA-096), and retry logic. ≤500 LOC.
- [ ] **AC-3**: `core/implement/circuit_breaker.py` contains the micro-commit circuit breaker (INFRA-095): LOC tracking, `MAX_EDIT_DISTANCE_PER_STEP`, `LOC_WARNING_THRESHOLD`, `LOC_CIRCUIT_BREAKER_THRESHOLD`, follow-up story generation, and the auto-commit-and-exit path.
- [ ] **AC-4**: `core/implement/__init__.py` re-exports the public API so inter-module callers are unaffected.
- [ ] **AC-5**: All existing tests in `tests/commands/test_implement.py` pass without modification.
- [ ] **AC-6**: No circular imports — `python -c "import agent.cli"` succeeds.
- [ ] **AC-7**: New unit tests in `tests/core/implement/test_orchestrator.py` and `tests/core/implement/test_circuit_breaker.py`.
- [ ] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [ ] **AC-9**: When `apply_change_to_file` rejects a full-file overwrite (safe-apply guard), the file is added to a `rejected_files` list, a `⚠️ INCOMPLETE STEP` warning is printed immediately with a hint to use `<<<SEARCH/===/>>>` format, and a `🚨 INCOMPLETE IMPLEMENTATION` summary listing all rejected files is printed before the governance gates. The `block_loc` uninitialised-variable bug (where LOC from a prior loop iteration was incorrectly accumulated on failure) is also corrected.
- [ ] **AC-10**: Docstring enforcement is **pre-apply** (not just a prompt suggestion). `enforce_docstrings(filepath, content)` uses `ast.parse()` to check every module, class, function, and method (including inner decorator closures) before the file is written to disk. Violations are printed with per-symbol detail and the block is rejected into `rejected_files` — same pattern as the safe-apply guard. Both the full-context and chunked apply paths enforce this gate. Non-Python files automatically pass.
- [ ] **Negative Test**: Circuit breaker correctly auto-commits partial work and halts execution when cumulative LOC exceeds 400.

## Non-Functional Requirements

- **Performance**: Step execution latency unchanged; circuit breaker LOC tracking adds no perceptible overhead.
- **Security**: Safe-apply guards (file overwrite protection) must be preserved in `orchestrator.py`.
- **Reliability**: Rejected files must never be silently swallowed — an INCOMPLETE summary must always be surfaced to the developer before gates run (AC-9).
- **Compliance**: Micro-commit atomicity (INFRA-089, INFRA-095) must be fully preserved.
- **Observability**: OpenTelemetry spans across step execution and circuit breaker activation must be retained.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-045: Implement Story from Runbook
- JRN-072: Terminal Console TUI Chat

## Impact Analysis Summary

- **Components touched**: `commands/implement.py` (refactor, thinned), `core/implement/orchestrator.py` (new), `core/implement/circuit_breaker.py` (new), `core/implement/__init__.py` (new).
- **Workflows affected**: `/implement` workflow, micro-commit loop, circuit breaker activation path.
- **Risks identified**: The circuit breaker's follow-up story generation calls `get_next_id` and writes to the cache — careful module boundary placement needed to avoid pulling CLI-level dependencies into `core/`.

## Test Strategy

- **Regression**: Run existing `tests/commands/test_implement.py` without modification; 100% pass rate required.
- **Unit Testing**: Isolated tests for orchestrator step execution (apply, retry) and circuit breaker thresholds (warning at 200, halt at 400).
- **Integration**: Run `agent implement <story> --apply --yes` against a small runbook to exercise the full pipeline.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `commands/implement.py` from git history and remove the `core/implement/` package.

## Copyright

Copyright 2026 Justin Cook
