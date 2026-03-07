# STORY-ID: INFRA-100: Decompose AI Service Module

## State

ACCEPTED

## Goal Description

Decompose the 1,169 LOC `core/ai/service.py` monolith into a modular, provider-based architecture using the Strategy pattern. This involves creating a standard `AIProvider` Protocol, extracting logic into specific provider modules (OpenAI, Vertex, Anthropic, Ollama), and isolating streaming/retry logic. The `AIService` will remain as a lightweight facade to preserve existing API contracts and test compatibility.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-062: Implement Oracle Preflight Pattern (Relies on multi-provider tool support)

## Panel Review Findings

### @Architect
- **ADR Compliance**: Follows ADR-041 (Module Decomposition).
- **Design**: Transitioning from a "God Object" to a Registry/Strategy pattern is the correct architectural move. Ensure the facade in `service.py` uses a factory to instantiate providers to avoid eager loading of all provider dependencies if only one is used.
- **Circular Dependencies**: High risk when `service.py` imports providers and providers need types from `service.py`. Move all shared types to `protocols.py` or `typedefs.py`.

### @Qa
- **Regression**: AC-5 is critical. Existing tests in `tests/core/ai/` must pass without altering the test code. This confirms the facade maintains behavioral parity.
- **Coverage**: New tests required for `streaming.py` specifically focusing on malformed chunks and backoff jitter.

### @Security
- **Secrets**: Ensure `get_secret` calls remain encapsulated. Providers should receive configuration/secrets via initialization, not by reaching into global state where possible.
- **Logging**: Ensure the extracted retry decorators do not log full prompt payloads (PII/Sensitive data).

### @Product
- **Extensibility**: This decomposition is a prerequisite for adding local model support (Llama-3/LocalAI) which is currently blocked by the monolithic complexity.

### @Observability
- **Tracing**: OpenTelemetry spans must be preserved. The `AIService.query` span should wrap the provider's `generate` call so the trace hierarchy remains intact.
- **Logs**: Structured logging should be implemented in the new `streaming.py` module.

### @Docs
- **Sync**: Documentation in `docs/architecture/ai-layer.md` (if exists) or the README needs to reflect the new `core/ai/` directory structure.

### @Compliance
- **Licensing**: All new files in `core/ai/providers/` and `core/ai/protocols.py` must include the standard Copyright 2026 header.

### @Backend
- **Protocols**: Use `typing.Protocol` with `@runtime_checkable` for `AIProvider`.
- **Exceptions**: As per AC-11, define `AIProviderError` and map provider-specific errors (e.g., `openai.RateLimitError`) to this common type within the provider implementation.

## Codebase Introspection

### Target File Signatures (from source)

```python
# src/agent/core/ai/service.py (Current)
class AIService:
    async def query(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, stream: bool = False, **kwargs) -> Union[str, AsyncGenerator[str, None]]: ...
    def get_available_models(self) -> List[str]: ...
    async def get_embeddings(self, text: str) -> List[float]: ...

# src/agent/core/ai/__init__.py
from .service import AIService, ai_service
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/cli/test_onboard_e2e.py` | `agent.core.ai.service.ai_service` | `agent.core.ai.service.ai_service` | Preserve facade; no change needed. |
| `tests/core/test_ai.py` | `agent.core.ai.service.get_secret` | `agent.core.ai.providers.<name>.get_secret` | Update patches if logic moved to provider. |
| `tests/core/test_ai_service.py` | `agent.core.ai.service.AIService._ensure_initialized` | `agent.core.ai.service.AIService._ensure_initialized` | Keep for facade testing. |
| `tests/db/test_journey_index.py` | `agent.core.ai.service.get_embeddings_model` | `agent.core.ai.providers.openai.get_embeddings_model` | Update patch to new location. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Default Model | `core/config.py` | Config-driven (e.g., `gpt-4o`) | Yes |
| Streaming Response | `core/ai/service.py` | Returns `AsyncGenerator` | Yes |
| Retry Strategy | `core/ai/service.py` | Exponential backoff (3 retries) | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert `print` statements in `service.py` (if any) to `logger.debug`.
- [ ] Fix inconsistent docstrings in `llm_service.py` if touched.
- [ ] Explicitly type `**kwargs` in the facade to include `temperature`, `max_tokens`.

## Scope Boundary

> **INFRA-100** delivers `protocols.py`, `streaming.py`, and a consolidated `providers.py` (unified dispatch file, ≤500 LOC).
> Per-provider class extraction (`providers/openai.py`, `providers/vertex.py`, etc.) is **explicitly deferred to INFRA-108** to stay within circuit breaker limits.

## Implementation Steps

### 1. Define Protocols and Base Errors

#### NEW `src/agent/core/ai/protocols.py`

- Define `AIError(Exception)` and subclasses: `AIConnectionError`, `AIRateLimitError`.
- Define `AIProvider` Protocol with `@runtime_checkable`.

```python
from typing import Protocol, runtime_checkable, AsyncGenerator, Optional, List

class AIError(Exception): ...
class AIConnectionError(AIError): ...
class AIRateLimitError(AIError): ...

@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str: ...
    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]: ...
    def supports_tools(self) -> bool: ...
    def get_models(self) -> List[str]: ...
```

### 2. Extract Streaming and Retry Logic

#### NEW `src/agent/core/ai/streaming.py`

- Move retry/backoff decorator logic out of `service.py`.
- Map provider-specific exceptions to `AIError` subtypes (no hardcoded `openai.error.*`).
- Move chunk processing and stream assembly logic here.

```python
import functools, asyncio, logging
from agent.core.ai.protocols import AIRateLimitError

logger = logging.getLogger(__name__)

def ai_retry(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except AIRateLimitError:
                    delay = base_delay * (2 ** attempt)
                    logger.warning("Rate limited, retrying in %.1fs", delay, extra={"attempt": attempt})
                    await asyncio.sleep(delay)
            raise AIRateLimitError("Max retries exceeded")
        return wrapper
    return decorator
```

### 3. Consolidate Provider Dispatch and Refactor Facade

#### MODIFY `.agent/src/agent/core/ai/providers.py` (unified, ≤500 LOC)

- Keep all provider dispatch logic in a single `providers.py` (no per-provider files yet — that is INFRA-108).
- Replace hardcoded `if provider == "openai":` chains with a `PROVIDERS` registry dict mapping name → callable.
- Wrap provider-specific SDK exceptions in `AIError` subtypes from `protocols.py`.
- Structured logging with `extra` dicts on each provider call.

This is a NEW file and should be emitted as a complete code block.

#### MODIFY `.agent/src/agent/core/ai/service.py` (surgical patch only)

> ⚠️ `service.py` is 1,169 LOC. You MUST use `<<<SEARCH/===/>>>` blocks — do NOT emit a full replacement.
>
> The goal is NOT to reduce service.py in this story — that is future work once INFRA-108 completes.
> The ONLY required change is to import the new modules so they are wired in:

File: `.agent/src/agent/core/ai/service.py`
<<<SEARCH
from agent.core.config import get_valid_providers
===
from agent.core.config import get_valid_providers
from agent.core.ai import protocols  # noqa: F401 — ensures protocols module is importable
from agent.core.ai import streaming  # noqa: F401 — ensures streaming module is importable
>>>

### 4. Ensure CLI Importability

> Run the following to verify no circular imports:
> `python -c "from agent.cli import app; print('OK')"`

#### CREATE `.agent/src/agent/core/ai/tests/test_providers.py` (NEW file)

> ⚠️ Tests live at `.agent/src/agent/core/ai/tests/` — NOT `.agent/tests/core/ai/`.
> Use a COMPLETE code block since this is a new file.

#### CREATE `.agent/src/agent/core/ai/tests/test_streaming.py` (NEW file)

> ⚠️ Tests live at `.agent/src/agent/core/ai/tests/` — NOT `.agent/tests/core/ai/`.
> Use a COMPLETE code block since this is a new file.

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/core/ai/tests/test_providers.py`: (New) Verify individual providers satisfy Protocol.
- [ ] `pytest .agent/src/agent/core/ai/tests/test_streaming.py`: (New) Verify retry logic and chunking.
- [ ] `pytest .agent/src/agent/core/ai/tests/test_service.py`: Verify facade still works.
- [ ] `agent check --story INFRA-100`: Run governance gates.

### Manual Verification

- [ ] Run `agent console` and initiate a chat to verify end-to-end connectivity.
- [ ] Run `agent voice` (if hardware available) to verify streaming response.
- [ ] Force a 429 error from a mock provider to verify `AIRateLimitError` is caught and retried.

## Definition of Done

### Documentation

- [ ] `CHANGELOG.md` updated with "Decomposed AI service into modular providers".
- [ ] Docstrings for all new classes and methods.

### Observability

- [ ] Logs show "Using provider: [OpenAI/Vertex]" at debug level.
- [ ] Trace spans for `ai_query` correctly encompass provider calls.

### Testing

- [ ] Unit tests for each new provider module.
- [ ] 0 regressions in existing AI tests.
- [ ] Circular import check passed.

## Copyright

Copyright 2026 Justin Cook
