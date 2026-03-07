# INFRA-101: Decompose Governance Module

## State

DRAFT

## Parent Plan

INFRA-099

## Problem Statement

The `core/governance.py` module has grown to 1,988 LOC and is responsible for three distinct concerns: AI Council orchestration (panel convening, role loading), preflight validation (gate execution, audit logging), and role/persona management. This violates the Single Responsibility Principle, makes independent testing difficult, and creates a high regression risk any time governance logic needs to change.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic governance module into focused sub-modules** so that **each concern is independently testable, the codebase adheres to ADR-041's 500 LOC ceiling, and future governance rules can be added without touching unrelated logic.**

## Acceptance Criteria

- [ ] **AC-1**: `core/governance/panel.py` contains council-convening logic: `convene_council_full`, `convene_council_fast`, and related prompt assembly helpers. Reduced to ≤500 LOC.
- [ ] **AC-2**: `core/governance/roles.py` contains role-loading logic: `load_roles`, `get_role`, persona mapping from `agents.yaml`, and the `@Security` / `@Architect` etc. resolution helpers.
- [ ] **AC-3**: `core/governance/validation.py` contains preflight/gate execution logic: `run_preflight`, `log_governance_event`, `log_skip_audit`, and all `GateResult` aggregation.
- [ ] **AC-4**: `core/governance/__init__.py` re-exports all public symbols so all existing callers continue to work with `from agent.core.governance import ...` without modification.
- [ ] **AC-5**: All existing tests in `tests/core/test_governance.py` pass without modification (behavioural equivalence).
- [ ] **AC-6**: No circular imports — `python -c "import agent.cli"` succeeds.
- [ ] **AC-7**: New unit tests in `tests/core/governance/test_panel.py`, `tests/core/governance/test_roles.py`, and `tests/core/governance/test_validation.py`.
- [ ] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [ ] **AC-9**: All audit logging calls (`log_governance_event`, `log_skip_audit`) include `resource_id` and `story_id` fields as required by SOC2 controls.
- [ ] **Negative Test**: `load_roles` falls back gracefully when `agents.yaml` is missing or malformed.

## Non-Functional Requirements

- **Performance**: No measurable change in council convening latency.
- **Security**: Audit log scrubbing via `scrub_sensitive_data` must be preserved in `validation.py`. No PII in logs.
- **Compliance**: SOC2 — audit log fields (`resource_id`, `story_id`, `timestamp`) must be retained in all logging calls.
- **Observability**: Existing structured logging and OpenTelemetry spans preserved across new module boundaries.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-036: Preflight Governance Check

## Impact Analysis Summary

- **Components touched**: `core/governance.py` (refactor → package), `core/governance/__init__.py` (new), `core/governance/panel.py` (new), `core/governance/roles.py` (new), `core/governance/validation.py` (new).
- **Workflows affected**: All `/panel`, `/preflight`, and `/pr` workflows that import from `core.governance`.
- **Risks identified**: Any caller using `from agent.core.governance import convene_council_full` must continue to work via the `__init__.py` re-export facade. Risk of accidentally splitting a tightly coupled function across two sub-modules.

## Test Strategy

- **Regression**: Run existing `tests/core/test_governance.py` suite without modification; 100% pass rate required.
- **Unit Testing**: New isolated tests for `panel.py` (council prompt assembly, fast-path logic), `roles.py` (YAML parsing, fallback), and `validation.py` (gate aggregation, audit log fields).
- **Integration**: Run `agent preflight --story INFRA-101` to exercise the full governance pipeline end-to-end.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `core/governance.py` from the git history and remove the `core/governance/` package.

## Copyright

Copyright 2026 Justin Cook
