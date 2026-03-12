# INFRA-123: Refactor core context and orchestrator modules to pass LOC quality gate

## State

DRAFT

## Problem Statement

The `context.py` and `orchestrator.py` modules have exceeded the maximum allowed Lines of Code (LOC) defined by our static analysis quality gates. This is currently blocking CI/CD pipelines and increasing technical debt, making the core infrastructure difficult to maintain and test.

## User Story

As a **Backend Engineer**, I want to **decompose monolithic core modules into smaller, logical sub-modules** so that **the codebase passes preflight quality gates and remains maintainable.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given the refactored code, When the preflight quality gate is triggered, Then the LOC check passes without warnings or errors.
- [ ] **Scenario 2**: Full feature parity must be maintained; all existing orchestration logic and context management must remain functional.
- [ ] **Negative Test**: System handles missing imports or circular dependencies gracefully by failing during the build phase rather than at runtime.

## Non-Functional Requirements

- **Performance**: No measurable degradation in execution speed or initialization time due to modularization.
- **Security**: Maintain existing access controls and data encapsulation within the new module structure.
- **Compliance**: Adherence to internal PEP8 and "Clean Code" architectural standards.
- **Observability**: Ensure logging and telemetry accurately reflect the new module paths for easier debugging.

## Linked ADRs

- ADR-041: Module Decomposition Standards
- ADR-042: Core Module Decomposition

## Linked Journeys

- JRN-001: Core System Initialization

## Impact Analysis Summary

**Components touched**: `agent/core/context.py`, `agent/core/implement/orchestrator.py`, and dependent files. New files created: `agent/core/context_docs.py`, `agent/core/context_source.py`, `agent/core/implement/parser.py`, `agent/core/implement/resolver.py`.
**Workflows affected**: Core orchestration engine, state management, and CI/CD pipeline (preflight checks).
**Risks identified**: High risk of circular dependencies; potential for broken imports in downstream microservices. Breaking change with `load_context` becoming async.

## Test Strategy

- **Static Analysis**: Run Flake8/SonarQube locally to verify LOC metrics.
- **Unit Testing**: Execute existing test suites for context and orchestrator to ensure 100% regression coverage. Specifically, ensure that tests run the asynchronous `load_context` method correctly using `asyncio.run()`, validating its functionality.
- **Performance Testing**: Measure initialization time and context assembly payload creation to ensure no measurable degradation in execution speed or initialization due to the async refactor or modularization boundary crossing.
- **Integration Testing**: Verify end-to-end orchestration workflows in the staging environment.

## Rollback Plan

In the event of a failure, revert to the previous Git commit hash where the monolithic files were intact and re-verify the environment state.

## Copyright

Copyright 2026 Justin Cook