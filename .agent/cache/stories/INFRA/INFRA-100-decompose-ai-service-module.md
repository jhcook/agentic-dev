# INFRA-100: Decompose AI Service Module

## State

IN_PROGRESS

## Parent Plan

INFRA-099

## Problem Statement

The current `core/ai/service.py` module has grown to 1,169 LOC, creating a monolithic "God Object" that is difficult to maintain, test, and extend. This complexity hinders developer velocity and increases the risk of regressions when adding new AI providers or modifying streaming logic.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic AI service into focused, modular components** so that **the codebase adheres to the Single Responsibility Principle, making it easier to maintain and scale.**

## Acceptance Criteria

- [ ] **AC-1**: `core/ai/protocols.py` defines an `AIProvider` Protocol with `generate()`, `stream()`, and `supports_tools()` methods.
- [ ] **AC-2**: `core/ai/providers/` package contains one module per provider backend (openai, vertex, anthropic, ollama), each implementing `AIProvider`.
- [ ] **AC-3**: `core/ai/streaming.py` contains streaming response handling, chunk processing, and retry/backoff decorators.
- [ ] **AC-4**: `core/ai/service.py` is reduced to a public API facade under 500 LOC that imports and delegates to `AIProvider` implementations.
- [ ] **AC-5**: All existing tests pass without modification (behavioural equivalence).
- [ ] **AC-6**: No circular imports — `python -c "import agent.cli"` succeeds.
- [ ] **AC-7**: New unit tests in `tests/core/ai/test_providers.py` and `tests/core/ai/test_streaming.py`.
- [ ] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [ ] **AC-9**: Consumers import `AIProvider` protocol for type annotations, never concrete provider classes.
- [ ] **AC-10**: Concrete provider classes explicitly satisfy `AIProvider` via `typing.runtime_checkable` or explicit inheritance for static type checker verification. *(Panel: @backend)*
- [ ] **AC-11**: Retry/backoff decorators use provider-agnostic exception types — no hardcoded provider-specific exceptions (e.g. `openai.error.APIConnectionError`). *(Panel: @backend)*
- [ ] **Negative Test**: System handles provider connection timeouts and malformed stream chunks gracefully.

## Non-Functional Requirements

- **Performance**: No measurable increase in latency for provider instantiation or stream processing.
- **Security**: Ensure sensitive provider configuration handling remains encapsulated within the new modules.
- **Compliance**: N/A.
- **Observability**: Maintain existing logging patterns and OpenTelemetry spans across the new module boundaries.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Impact Analysis Summary

- **Components touched**: `core/ai/service.py` (refactor), `core/ai/protocols.py` (new), `core/ai/providers/` (new package), `core/ai/streaming.py` (new).
- **Workflows affected**: All AI-driven features (chat, completion, streaming responses).
- **Risks identified**: Potential for circular imports between the facade and sub-modules; potential regressions in retry backoff timing.

## Test Strategy

- **Regression**: Run all existing tests in `tests/core/ai/` to ensure 100% pass rate without modification.
- **Unit Testing**: Implement new unit tests for `providers.py` (factory logic) and `streaming.py` (retry and chunk handling).
- **Integration**: Verify the facade correctly orchestrates the extracted modules.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `core/ai/service.py` from the backup/previous state and remove the newly created files.

## Copyright

Copyright 2026 Justin Cook
