# STORY-ID: INFRA-100: Decompose AI Service Module

## State

ACCEPTED

## Goal Description

Decompose the monolithic `core/ai/service.py` (1,169 LOC) into a modular architecture using the Strategy pattern. This involves defining a formal `AIProvider` protocol, extracting concrete implementations (OpenAI, Vertex, Anthropic, Ollama) into a new `providers/` package, and isolating streaming/retry logic. The goal is to improve maintainability and strictly adhere to the Single Responsibility Principle as per ADR-041.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Panel Review Findings

### @Architect
- **Compliance**: The plan aligns with ADR-041 (Module Decomposition).
- **Design**: Moving from a "God Object" to a Protocol-based strategy is the correct architectural evolution.
- **Boundary Check**: Ensure `core/ai/service.py` acts only as a Dispatcher/Facade and does not leak provider-specific logic.

### @Qa
- **Coverage**: Existing regression tests in `src/agent/core/ai/tests/test_service.py` must pass 100% to ensure behavioral parity.
- **Strategy**: New unit tests are required for the standalone streaming logic and each individual provider implementation to prevent regression during future updates.
- **Edge Cases**: Verify that provider-specific errors are correctly caught and re-raised as generic AI errors to satisfy AC-11.

### @Security
- **Secret Handling**: Ensure that provider API keys continue to be managed via `core.secrets` and are never logged or stored in the service instances.
- **Dependency Check**: Confirm no new dependencies are introduced; keep existing pinned versions for `openai`, `google-cloud-aiplatform`, etc.

### @Product
- **User Impact**: No changes to user-facing CLI behavior. The TUI and Voice workflows should remain identical in performance and response.
- **Velocity**: This refactor is critical for supporting upcoming "Bring Your Own Model" (BYOM) features.

### @Observability
- **Tracing**: OpenTelemetry spans in the original `service.py` must be migrated to the new providers. Ensure the span names remain consistent for historical metric comparison.
- **Logging**: Use structured logging. Ensure the `model_id` and `provider_name` are included in all logs extracted from the monolith.

### @Docs
- **Internal Docs**: Update any module-level docstrings in `src/agent/core/ai/__init__.py` to reflect the new package structure.
- **Developer Guide**: Brief mention in the internal contributor guide about adding new providers via the `AIProvider` protocol.

### @Compliance
- **Licensing**: All new files (`protocols.py`, `streaming.py`, etc.) must include the standard copyright and license header.
- **GDPR**: AI logic extraction does not change the data processing basis; ensure PII scrubbing logic remains intact in the facade.

### @Mobile
- **N/A**: This is a core backend refactor. No impact on mobile navigation or state management expected.

### @Web
- **API Stability**: Since the FastAPI backend uses the AI service, ensure the internal signatures in the Facade remain backward compatible to avoid breaking the Next.js frontend calls.

### @Backend
- **Strict Typing**: Use `typing.runtime_checkable` for the `AIProvider` protocol to allow for `isinstance()` checks if needed.
- **Exception Mapping**: Implement a custom exception hierarchy (e.g., `AIError` -> `RateLimitError`) in `protocols.py` to wrap provider-specific exceptions.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert any remaining `print()` calls in the old `service.py` to `logger.debug()` or `logger.info()`.
- [ ] Remove unused imports in `src/agent/core/ai/service.py` after extraction.
- [ ] Update `src/agent/core/ai/llm_service.py` if it contains duplicated logic that can now use the new `AIProvider` protocol.

## Implementation Steps

### core/ai (Protocols & Types)

#### NEW `src/agent/core/ai/protocols.py`

- Define the `AIProvider` Protocol.
- Include `typing.runtime_checkable`.
- Define base exception classes for the AI domain.

```python
from typing import Protocol, runtime_checkable, Any, AsyncIterator
from dataclasses import dataclass

@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, **kwargs) -> str: ...
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...
    def supports_tools(self) -> bool: ...

class AIError(Exception): """Base AI Error"""
class AIRateLimitError(AIError): """Mapped from provider 429s"""
```

### core/ai (Streaming Logic)

#### NEW `src/agent/core/ai/streaming.py`

- Extract `stream_response_handler` and chunk processing logic from `service.py`.
- Implement provider-agnostic retry decorators using `tenacity`.

### core/ai/providers (Concrete Implementations)

#### NEW `src/agent/core/ai/providers/__init__.py`

- Export the provider classes for easy discovery by the factory.

#### NEW `src/agent/core/ai/providers/openai.py`
#### NEW `src/agent/core/ai/providers/vertex.py`
#### NEW `src/agent/core/ai/providers/anthropic.py`
#### NEW `src/agent/core/ai/providers/ollama.py`

- Move implementation details for each provider from `service.py` to these modules.
- Ensure they implement `AIProvider`.
- Wrap calls in `try/except` blocks to map exceptions to `protocols.AIError`.

### core/ai (Facade Refactor)

#### MODIFY `src/agent/core/ai/service.py`

- Remove all concrete provider logic.
- Implement a `ProviderFactory` or simple mapping logic in the `AIService` class.
- Update `AIService.generate` and `AIService.stream` to delegate to the appropriate `AIProvider` instance.
- Ensure LOC is reduced below 500.

## Verification Plan

### Automated Tests

- [ ] **Regression**: `pytest .agent/tests/` - All existing tests must pass without changes.
- [ ] **Unit (Providers)**: `pytest .agent/tests/test_providers.py` (New file) - Test each provider in isolation with mocks.
- [ ] **Unit (Streaming)**: `pytest .agent/tests/test_streaming.py` (New file) - Verify retry logic and chunking.
- [ ] **Circular Import Check**: `python -c "import agent.cli; print('Success')"`

### Manual Verification

- [ ] Run `agent chat` in the terminal and verify streaming responses work for the default provider.
- [ ] Switch provider in `config.yaml` to Vertex/Anthropic and verify `agent chat` functionality.
- [ ] Trigger a simulated rate limit and verify the retry logic kicks in (logs should show retries).

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Decomposed AI service into modular providers".
- [ ] Module-level docstrings added to all new files.

### Observability

- [ ] Logs are structured and include `provider` and `model` fields.
- [ ] OpenTelemetry spans are verified in the trace collector.

### Testing

- [ ] Unit tests passed for all new modules.
- [ ] Integration tests (existing service tests) passed.

## Copyright

Copyright 2026 Justin Cook
