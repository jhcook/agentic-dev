# INFRA-108: Protocol-Based AI Provider Refactor

## State

DONE

## Parent Plan

INFRA-099

## Problem Statement

INFRA-100 decomposed the monolithic `service.py` into `providers.py`, `streaming.py`, and `protocols.py`. However, the `providers.py` module (812 LOC) remains a monolithic dispatch file using string-based `if/elif` routing and `object`-typed client parameters. The `AIProvider` protocol defined in `protocols.py` is not yet used by the dispatch logic. This was descoped from INFRA-100 to stay within circuit breaker limits.

## User Story

As a **Backend Engineer**, I want to **refactor the AI provider dispatch into per-provider classes implementing the `AIProvider` protocol** so that **new providers can be added by implementing a single interface, and static type checking covers the full provider lifecycle.**

## Acceptance Criteria

- [ ] **AC-1**: `core/ai/providers/` is a Python package with one module per provider backend (openai.py, vertex.py, anthropic.py, ollama.py, gh.py).
- [ ] **AC-2**: Each provider module contains a class implementing the `AIProvider` protocol from `protocols.py`.
- [ ] **AC-3**: `core/ai/providers/__init__.py` exports a factory function `get_provider(name: str) -> AIProvider` and the `PROVIDERS` registry.
- [ ] **AC-4**: `core/ai/service.py` delegates to `AIProvider` instances via the factory, replacing string-based dispatch.
- [ ] **AC-5**: `_should_retry()` uses `protocols.AIRateLimitError` instead of string-parsing error messages.
- [ ] **AC-6**: All existing tests pass (behavioral equivalence).
- [ ] **AC-7**: New unit tests cover each concrete provider class in isolation.
- [ ] **AC-8**: `python -c "import agent.cli"` succeeds (no circular imports).
- [ ] **AC-9**: Combined `providers/` package LOC stays under the 500 LOC ceiling per ADR-041.

## Non-Functional Requirements

- **Performance**: No measurable latency increase for provider instantiation.
- **Security**: API key handling remains encapsulated within provider modules via `core.secrets`.
- **Observability**: Structured logging with `extra` dicts preserved across all provider modules.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Impact Analysis Summary

- **Components touched**: `core/ai/providers.py` (refactor into package), `core/ai/service.py` (update dispatch), `core/ai/protocols.py` (may extend).
- **Workflows affected**: All AI-driven features (chat, completion, streaming).
- **Risks**: Circular imports between factory and concrete providers; mock/patch target migration in tests.

## Test Strategy

- **Regression**: All existing `tests/core/ai/` tests must pass.
- **Unit**: Each provider class tested independently with mocked SDK clients.
- **Integration**: Factory function returns correct provider for each name.

## Rollback Plan

- Revert to flat `providers.py` module from INFRA-100.

## Copyright

Copyright 2026 Justin Cook
