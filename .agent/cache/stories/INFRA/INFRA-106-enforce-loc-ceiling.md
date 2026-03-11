# INFRA-106: Enforce LOC Ceiling via CI and Documentation

## State

IN_PROGRESS

## Parent Plan

INFRA-099

## Problem Statement

The structural decomposition delivered by INFRA-100 through INFRA-105 eliminates the current monolithic files, but without automated enforcement, the 500 LOC ceiling defined in ADR-041 will erode over time. There is no CI gate, no pre-commit hook, and no import hygiene check preventing files from growing past the ceiling again. This story transitions ADR-041 from a guideline into a technical control, ensuring the system does not regress toward a monolithic state.

## User Story

As a **Platform Engineer**, I want to **enforce the 500 LOC ceiling and import hygiene rules automatically in CI and pre-commit** so that **no future PR can silently re-introduce a God Object and all module decomposition standards are self-sustaining.**

## Acceptance Criteria

- [ ] **AC-1**: A script `scripts/check_loc.py` reports all Python files under `.agent/src/agent/` that exceed 500 physical lines of code. It must:
    - Exit non-zero if violations are found.
    - Print a clear violation message including the file path, line count, and the local command to fix/reproduce (e.g., `agent preflight --gate quality`).
    - Use static analysis only; it must NOT execute the files it analyzes.
    - Support a `--format json` flag for machine-readable output.
- [ ] **AC-2**: A script `scripts/check_imports.py` identifies inter-package circular imports using **static AST analysis** (not `importlib` or runtime inspection). It must:
    - Detect direct (A->B->A) and transitive (A->B->C->A) circularities.
    - Exit non-zero on failure.
    - Adhere to the same security constraints as `check_loc.py` (no code execution).
- [ ] **AC-3**: Both scripts are wired into the `agent preflight` pipeline as a new `LOC Ceiling` gate in `commands/check.py` (routed through `core/check/quality.py`).
    - The integration must capture execution time and violation counts as OpenTelemetry attributes (e.g., `code.quality.loc_max`, `code.quality.violation_count`).
- [ ] **AC-4**: A `.pre-commit-config.yaml` hook entry runs `check_loc.py` on staged Python files. The hook must be path-scoped to `.agent/src/agent/` and ignore irrelevant directories (e.g., `node_modules`, `migrations`).
- [ ] **AC-5**: `README.md` and `CHANGELOG.md` are updated. 
    - `README.md` must document the 500 LOC standard and how to run checks locally.
    - `CHANGELOG.md` must categorize these additions under "Internal" or "Changed."
- [ ] **AC-6**: `docs/adr/ADR-041-module-decomposition.md` is updated to define "LOC" as **Physical Lines** and formalize the **Approved Exceptions Process**.
    - Exceptions must be managed via a configuration file (e.g., `pyproject.toml` or `.loc-ignore`) or an inline `# nolint: loc-ceiling` comment.
    - Database migrations (`**/migrations/*.py`) and generated files are explicitly exempted.
- [ ] **AC-7**: Unit tests in `tests/scripts/test_check_loc.py` and `tests/scripts/test_check_imports.py` verify the scripts correctly identify violations and handle:
    - Binary, empty, and non-UTF8 files.
    - Direct and transitive circular dependencies.
    - Exception/allow-list logic.
- [ ] **AC-8**: Scripts must include standard license headers and follow GDPR data minimization (logging relative paths only; no absolute system paths or code snippets).

## Non-Functional Requirements

- **Performance**: LOC check script completes in under 5 seconds on the full `.agent/src/` tree. The script should use `os.scandir` or `pathlib` for efficient traversal.
- **Security**: 
    - **No Code Execution**: Analysis must use the `ast` module; `import` or `importlib` are prohibited to prevent execution of module-level code.
    - **DoS Protection**: Scripts must implement a maximum file size limit (e.g., 10MB) to prevent resource exhaustion during scans.
    - **Path Safety**: Traversal must set `follow_symlinks=False` to prevent path traversal attacks or infinite loops.
- **Observability**: Scripts must use the standard Python `logging` library. Violations must be logged at `ERROR` level; compliant summaries at `INFO`.
- **Dependency Management**: Prefer Python Standard Library (`ast`, `sys`, `pathlib`) to minimize the supply chain attack surface.

## Linked ADRs

- ADR-041: Module Decomposition Standards
- ADR-028: CLI Command Structure (Sync entry points)

## Linked Journeys

- JRN-036: Preflight Governance Check

## Impact Analysis Summary

- **Components touched**: `scripts/check_loc.py` (new), `scripts/check_imports.py` (new), `core/check/quality.py` (gate wiring), `.pre-commit-config.yaml`, `README.md`, `CHANGELOG.md`, `docs/adr/ADR-041-module-decomposition.md`.
- **Workflows affected**: `agent preflight`, local git commit workflow.
- **Exclusions**: Database migrations (`**/migrations/*.py`) and auto-generated assets are excluded from LOC checks to preserve migration integrity and prevent CI friction on machine-produced code.
- **Risks**: Must be merged **after** INFRA-105 to ensure the baseline codebase is compliant, otherwise global CI will break.

## Test Strategy

- **Unit Testing**: 
  - Synthetic fixtures for `check_loc.py`: Valid (<500), Over limit (>500), Empty, Binary, and Non-Python files.
  - Synthetic fixtures for `check_imports.py`: Valid imports, Direct circularity, and Transitive circularity.
  - Logic verification for the "Exceptions/Allow-list" mechanism.
- **Integration Testing**: 
  - **Positive Path**: `agent preflight` passes on the post-INFRA-105 codebase.
  - **Negative Path**: Manually introduce a 501-line file and verify `agent preflight` fails with the specific error message and exit code.
  - **Hook Validation**: Verify `pre-commit run --all-files` correctly identifies violations locally.
- **Performance Testing**: Measure and log execution time of the scripts on the full tree to ensure compliance with the <5s NFR.

## Rollback Plan

- Remove `scripts/check_loc.py` and `scripts/check_imports.py`.
- Revert the gate wiring in `core/check/quality.py` and the `.pre-commit-config.yaml` entry.
- Revert `CHANGELOG.md`, `README.md`, and `ADR-041` edits.

## Copyright

Copyright 2026 Justin Cook