# INFRA-170: Preflight Accuracy: Thorough Default, Code Complexity Gates, and File Decomposition

## State

COMMITTED

## Problem Statement

The current agent preflight and check routines default to a shallow analysis, which occasionally allows preventable syntax errors or architectural debt to reach later stages of the CI/CD pipeline. Additionally, the presence of monolithic files (up to 1,956 LOC) and excessively long functions increases cognitive load and maintenance risk. AI-generated syntax error reports currently lack a cross-validation mechanism, leading to noise from false positives.

## User Story

As a Developer or DevOps Engineer, I want the agent's preflight checks to be rigorous by default and enforce deterministic code complexity standards so that I can maintain a high-quality, modular codebase and trust automated error reporting.

## Acceptance Criteria

- [ ] **AC-1**: `agent preflight` and `agent check` default to `--thorough` mode (full-file context for AI panel).
- [ ] **AC-2**: `--quick` flag opts out of thorough mode for fast/cheap runs.
- [ ] **AC-3**: Deterministic file LOC gate: **WARN** at >500 LOC per file in the diff.
- [ ] **AC-4**: Deterministic function length gate: **WARN** at 21–50 lines, **BLOCK** at >50 lines.
- [ ] **AC-5**: Decompose `_governance_legacy.py` (1956 LOC) into `governance/panel.py`, `governance/validation.py`, `governance/prompts.py`, `governance/reports.py`.
- [ ] **AC-6**: Decompose `implement.py` (1000+ LOC) into focused sub-modules.
- [ ] **AC-7**: Cross-validate AI syntax-error claims against `py_compile` / pytest results; auto-dismiss contradicted findings.
- [ ] **AC-8**: All existing tests continue to pass after decomposition (zero regressions).
- [ ] **AC-9**: `agent new-story` injects codebase file tree into the AI prompt so generated Impact Analysis paths are real, not hallucinated.

## Non-Functional Requirements

- **Performance**: `--thorough` mode must complete within an acceptable developer-loop timeframe (< 60s for standard modules).
- **Security**: Complexity gates must be enforced in the CI environment to prevent "code smell" bypasses.
- **Compliance**: Code modularity must align with internal architectural standards for maintainability.
- **Observability**: Complexity gate violations (Warnings/Blocks) must be explicitly logged in the preflight summary.

## Linked ADRs

- ADR-012: Code Quality and Complexity Standards
- ADR-005: ADR-005: AI-Driven Governance Preflight
- ADR-025: ADR-025: Lazy AIService Initialization
- ADR-027: ADR-027: Security Blocklist Pattern
- ADR-001: ADR-001: Git-like Distributed Synchronization Architecture

## Linked Journeys

- JRN-004: Developer Local Preflight Workflow
- JRN-065: JRN-065-circuit-breaker-during-implementation
- JRN-001: JRN-001-smart-ai-router-and-python-rewrite

## Impact Analysis Summary

**Components touched:**
- `.agent/src/agent/commands/check.py` — flip `thorough` default to `True`, add `--quick` flag
- `.agent/src/agent/commands/implement.py` — flip `thorough` default, consider decomposition
- `.agent/src/agent/core/_governance_legacy.py` — decompose into `governance/` sub-package
- `[NEW] .agent/src/agent/core/governance/panel.py` — council orchestration loop
- `[NEW] .agent/src/agent/core/governance/validation.py` — `_validate_finding_against_source` + helpers
- `[NEW] .agent/src/agent/core/governance/prompts.py` — system prompt construction
- `[NEW] .agent/src/agent/core/governance/reports.py` — report formatting and JSON assembly
- `[NEW] .agent/src/agent/core/governance/complexity.py` — deterministic LOC/function-length gates
- `[NEW] .agent/src/agent/core/governance/syntax_validator.py` — cross-validate AI claims vs py_compile/pytest

**Workflows affected:**
- Local development `preflight` checks.
- CI/CD Pull Request validation pipeline.

**Risks identified:**
- Increased CI execution time due to `--thorough` default.
- Potential breaking changes during the decomposition of legacy governance logic.
- False negatives if local linting tools are not perfectly aligned with the execution environment.

## Test Strategy

- **Unit Testing**: Verify complexity gate logic triggers at 21, 51, and 501 lines respectively.
- **Integration Testing**: Execute `agent preflight` on a known "dirty" branch to ensure blocks trigger correctly.
- **Regression Testing**: Verify that the functionality previously in `_governance_legacy.py` remains intact after decomposition via existing suite in `.agent/tests/governance/`.
- **Validation Test**: Mock an AI syntax error and provide a passing test result to verify auto-dismissal logic.

## Rollback Plan

- Revert `check.py` to restore `thorough=False` default.
- If decomposition causes regressions, restore `_governance_legacy.py` from pre-INFRA-170 commit.

## Copyright

Copyright 2026 Justin Cook
