# INFRA-108: Protocol-Based AI Provider Refactor

## State

ACCEPTED

## Goal Description

Refactor `core/ai/providers.py` from a flat module with stub provider classes into a proper Python package (`core/ai/providers/`) where each provider backend (openai, vertex, anthropic, ollama, gh) is implemented as a concrete class in its own module, fully satisfying the `AIProvider` protocol defined in `protocols.py`. The factory function `get_provider()` and `PROVIDERS` registry are exported from the package `__init__.py`. `service.py` dispatch (`_try_complete`, `stream_complete`) delegates to `AIProvider` instances via the factory, eliminating all string-based `if/elif` routing. `_should_retry()` is refactored to check `isinstance(exc, AIRateLimitError)` instead of string-parsing. The combined `providers/` package must stay under 500 LOC.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Panel Review Findings

### @Architect

**APPROVE with notes.**

- **ADR-041 compliance**: The target package structure (`providers/{openai,vertex,anthropic,ollama,gh}.py`) is explicitly mandated by ADR-041 §4 (AI Service Layer decomposition targets). This story is a direct implementation of that ADR.
- **Interface-first design**: `AIProvider` in `protocols.py` is the correct Protocol anchor. Concrete classes must NOT be imported directly by `service.py` — only the factory `get_provider()` is the consumer boundary.
- **Circular import risk (AC-8)**: The factory in `providers/__init__.py` imports concrete modules; concrete modules must NOT import from `providers/__init__.py`. Each concrete module may only import from `protocols.py`, `streaming.py`, and `secrets.py` — never from `service.py` or each other.
- **LOC ceiling (AC-9)**: The combined `providers/` LOC budget of 500 is achievable. Each concrete module should be ≤100 LOC. Verify with `wc -l` across all files before committing.
- **`service.py` role after refactor**: `service.py` retains the `AIService` class (provider selection, fallback chain, metrics, OTel). The `_try_complete` method delegates to the provider instance returned by `get_provider()`. `stream_complete` similarly delegates. The `reload()` method continues to manage SDK client construction (credential loading) — these clients are injected into provider instances.

### @QA

**APPROVE with required test coverage.**

- **AC-6 regression**: All tests in `core/ai/tests/` must pass. The main risk is mock/patch path migration: tests currently patching `agent.core.ai.providers.OpenAIProvider` must be updated to patch `agent.core.ai.providers.openai.OpenAIProvider` (or the factory).
- **AC-7 new per-provider unit tests**: Each concrete provider module requires an independent test file in `core/ai/tests/`:
  - `test_openai_provider.py` — mocks `openai.OpenAI` SDK, tests `generate()`, `stream()`, `supports_tools()`, `get_models()`
  - `test_vertex_provider.py` — already exists, verify patch targets after move
  - `test_anthropic_provider.py` — mocks `anthropic.Anthropic` SDK
  - `test_ollama_provider.py` — mocks OpenAI-compat client
  - `test_gh_provider.py` — mocks `subprocess.run`
- **Factory tests**: `test_providers.py` must test `get_provider()` returns correct class for all known names, prefix fallbacks, and unknown model defaults.
- **Integration test**: Test that `AIService._try_complete()` successfully calls `generate()` on the returned provider instance via the factory.

### @Security

**APPROVE.** No new attack surface introduced.

- API key handling remains in `core.secrets` (`get_secret()`). Concrete provider modules call `get_secret()` in their constructors — keys are never stored as plaintext strings in the module.
- `gh` provider executes `subprocess.run(["gh", "models", "run", ...])` with a hardcoded command list — no user input is injected into the subprocess command. This is compliant with the existing security posture.
- Ollama localhost-only check (`OLLAMA_HOST` URL validation) must be preserved in the `OllamaProvider` constructor.
- No PII in log `extra` dicts — only structured technical metadata (provider name, model id, attempt count).

### @Product

**APPROVE.** AC-1 through AC-9 are clear and testable; all map 1:1 to implementation steps below.

- AC-4 (service.py delegates via factory) is the most impactful behavioral change. The fallback chain and retry logic in `AIService.complete()` must be preserved exactly — only the dispatch mechanism (`_try_complete`) is refactored.
- AC-5 (`_should_retry` using `AIRateLimitError`) simplifies the retry heuristic. The existing string-matching `rate_limit_indicators` list in `_try_complete` should be replaced with `isinstance(e, AIRateLimitError)` plus SDK-specific exception mapping in each provider class.

### @Observability

**APPROVE with instrumentation requirements.**

- Structured `logging.info/debug/warning` with `extra={"provider": ..., "model": ..., "attempt": ...}` must be preserved in each concrete provider module.
- OTel spans (`ai.completion`, `ai.stream_completion`) remain in `service.py` — they are not moved into provider modules.
- New metric: consider adding `ai_provider_type` label to existing `ai_command_runs_total` counter (it already uses `provider` label so this is already covered).

### @Compliance

**APPROVE.**

- All new modules require the Apache 2.0 license header (see `templates/license_header.txt`).
- `## Copyright` section required in `__init__.py` docstring block comment if the file has no other docstring.

### @Backend

**APPROVE with implementation details.**

- `_try_complete` in `service.py` currently rebuilds SDK clients on every call (e.g. `_build_genai_client(provider)` is called per-request). After INFRA-108, each provider's `generate()` / `stream()` method should accept an optional pre-built `client` kwarg, or the provider is constructed with the client injected at `reload()` time. **Recommended**: `get_provider(name, client=self.clients[name])` — the factory accepts an optional pre-built SDK client and injects it into the constructor.
- `ai_retry` decorator from `streaming.py` is already used in provider stubs. After moving to concrete modules, the decorator is imported from `agent.core.ai.streaming` — no change needed.
- `_should_retry` does not exist as a named method — the retry logic is inline in `_try_complete`. AC-5 refers to replacing the string-based `rate_limit_indicators` check with typed exception catching inside each provider's `generate()`/`stream()` (raise `AIRateLimitError` for 429s) and the catch block in `_try_complete` catching `AIRateLimitError` explicitly.

## Codebase Introspection

### Target File Signatures (from source)

**`core/ai/protocols.py` (current)**

```python
class AIError(Exception): ...
class AIConnectionError(AIError): ...
class AIRateLimitError(AIError): ...
class AIConfigurationError(AIError): ...

@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str: ...
    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[str, None]: ...
    def supports_tools(self) -> bool: ...
    def get_models(self) -> List[str]: ...
```

**`core/ai/providers.py` (current — to be replaced by package)**

```python
class BaseProvider:
    def __init__(self, model_name: str): ...
    def supports_tools(self) -> bool: ...
    def get_models(self) -> List[str]: ...

class OpenAIProvider(BaseProvider):
    async def generate(self, prompt, system_prompt=None, **kwargs) -> str: ...  # stub
    async def stream(self, prompt, system_prompt=None, **kwargs) -> AsyncGenerator[str, None]: ...  # stub

class VertexAIProvider(BaseProvider): ...  # stub
class MockProvider(BaseProvider): ...  # stub

_PROVIDER_REGISTRY: Dict[str, Type[AIProvider]]
def get_provider(model_name: str) -> AIProvider: ...
```

**`core/ai/service.py` — key methods to modify**

```python
class AIService:
    def _try_complete(self, provider, system_prompt, user_prompt, model=None, temperature=None, stop_sequences=None) -> str: ...
    # Currently: large if/elif per provider
    # After: calls get_provider(provider, client=self.clients[provider]).generate(...)

    def stream_complete(self, system_prompt, user_prompt, model=None, temperature=None, stop_sequences=None) -> Generator[str, None, None]: ...
    # Currently: large if/elif per provider
    # After: calls get_provider(provider, client=self.clients[provider]).stream(...)
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|--------------------|
| `test_providers.py` | `agent.core.ai.providers.OpenAIProvider` | `agent.core.ai.providers.openai.OpenAIProvider` | Update imports + patch paths |
| `test_vertex_provider.py` | `agent.core.ai.service.AIService._build_genai_client` | No change (stays in service.py) | Verify; likely no change |
| `test_service.py` | `agent.core.ai.service.AIService._try_complete` | No change (method stays) | Verify mock contract |
| `test_streaming.py` | `agent.core.ai.streaming` | No change | No action |
| `test_openai_provider.py` | _(new)_ | `agent.core.ai.providers.openai.OpenAIProvider` | Create new file |
| `test_anthropic_provider.py` | _(new)_ | `agent.core.ai.providers.anthropic.AnthropicProvider` | Create new file |
| `test_ollama_provider.py` | _(new)_ | `agent.core.ai.providers.ollama.OllamaProvider` | Create new file |
| `test_gh_provider.py` | _(new)_ | `agent.core.ai.providers.gh.GHProvider` | Create new file |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Fallback chain order | `service.py:449` | `gh → gemini → vertex → openai → anthropic → ollama` | **Yes** |
| Retry on 429/rate-limit | `service.py:1120-1146` | String-matching `rate_limit_indicators` | **Replace** with `isinstance(e, AIRateLimitError)` |
| Gemini client re-init per request | `service.py:910` | `_build_genai_client(provider)` called in `_try_complete` | **Preserve** (pass fresh client to provider) |
| Ollama localhost guard | `service.py:308` | `parsed.hostname not in ("localhost", "127.0.0.1", ...)` | **Preserve** (move to `OllamaProvider.__init__`) |
| OpenAI timeout | `service.py:261` | `OpenAI(..., timeout=120.0)` | **Preserve** (set in `reload()`, inject into provider) |
| Anthropic max_tokens | `service.py:1037` | `max_tokens=4096` | **Preserve** (set in `AnthropicProvider.generate()`) |
| GH CLI context limit error | `service.py:981-988` | Raises `Exception("GH Context Limit Exceeded")` | **Preserve** (raise `AIConfigurationError`) |
| OTel spans | `service.py:535-544` | Wrapped around `_try_complete`/`stream_complete` | **Preserve** (stays in service.py) |
| `AIService.models` dict | `service.py:111-117` | Default model per provider name | **Preserve** (passed to provider as `model_name`) |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Replace string-based `rate_limit_indicators` list in `_try_complete` with typed `AIRateLimitError` catching (AC-5)
- [x] Remove `is not` string comparisons for provider dispatch in `_try_complete` and `stream_complete`
- [ ] (Optional) Remove `_build_genai_client` from `AIService` after Gemini/Vertex provider classes own client construction

## Implementation Steps

### Step 1: Create `providers/` package skeleton

#### NEW `core/ai/providers/__init__.py`

Create the package init that exports the factory and registry. Keep it minimal and import-safe.

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""AI provider package — factory and registry for concrete AIProvider backends.

Responsible for dispatching provider name strings to concrete AIProvider instances.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from agent.core.ai.protocols import AIProvider

logger = logging.getLogger(__name__)

# Registry maps provider name -> concrete class (lazy-imported to avoid circular imports)
_PROVIDER_CLASS_MAP: Dict[str, str] = {
    "openai": "agent.core.ai.providers.openai.OpenAIProvider",
    "gemini": "agent.core.ai.providers.vertex.VertexAIProvider",  # Gemini uses same SDK path
    "vertex": "agent.core.ai.providers.vertex.VertexAIProvider",
    "anthropic": "agent.core.ai.providers.anthropic.AnthropicProvider",
    "ollama": "agent.core.ai.providers.ollama.OllamaProvider",
    "gh": "agent.core.ai.providers.gh.GHProvider",
    "mock": "agent.core.ai.providers.mock.MockProvider",
}

# Public registry: maps provider name -> class (populated on first access)
PROVIDERS: Dict[str, Type[AIProvider]] = {}


def _resolve_class(dotted: str) -> Type:
    """Import and return a class from a dotted module path."""
    module_path, class_name = dotted.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_provider(name: str, client: Optional[Any] = None, model_name: Optional[str] = None) -> AIProvider:
    """Return a concrete AIProvider instance for *name*.

    Args:
        name: Provider identifier (e.g. ``"openai"``, ``"vertex"``).
        client: Optional pre-built SDK client to inject (avoids re-initialization).
        model_name: Model identifier to use for this provider.

    Returns:
        A configured ``AIProvider`` instance.

    Raises:
        ValueError: If *name* is not a recognized provider.
    """
    if name not in _PROVIDER_CLASS_MAP:
        raise ValueError(f"Unknown AI provider: {name!r}. Valid: {list(_PROVIDER_CLASS_MAP)}")

    if name not in PROVIDERS:
        PROVIDERS[name] = _resolve_class(_PROVIDER_CLASS_MAP[name])

    cls = PROVIDERS[name]
    return cls(client=client, model_name=model_name)


__all__ = ["get_provider", "PROVIDERS", "AIProvider"]
```

#### NEW `core/ai/providers/base.py`

```python
# Copyright 2026 Justin Cook
# ... (license header) ...
"""Base provider mixin with shared helpers for all AIProvider backends."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class BaseProvider:
    """Shared implementation for all AIProvider backends.

    Subclasses must implement ``generate()`` and ``stream()``.
    """

    def __init__(self, client: Optional[Any] = None, model_name: Optional[str] = None) -> None:
        self.client = client
        self.model_name = model_name or ""

    def supports_tools(self) -> bool:
        """Return whether this provider supports tool/function calling."""
        return False

    def get_models(self) -> List[str]:
        """Return the model identifier(s) supported by this provider instance."""
        return [self.model_name] if self.model_name else []
```

### Step 2: Implement concrete provider modules

#### NEW `core/ai/providers/openai.py`

Move the full OpenAI dispatch logic from `service.py:_try_complete (provider=="openai")` and `stream_complete (provider in ("openai", "ollama"))`:

- `generate()`: calls `self.client.chat.completions.create(model=..., messages=[...])`; raises `AIRateLimitError` on HTTP 429; raises `AIConnectionError` on network errors.
- `stream()`: calls `self.client.chat.completions.create(..., stream=True)`; yields `chunk.choices[0].delta.content`.
- `supports_tools()`: returns `True`.
- Constructor validates `self.client is not None`.

```python
from agent.core.ai.protocols import AIProvider, AIRateLimitError, AIConnectionError
from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.streaming import ai_retry
```

#### NEW `core/ai/providers/vertex.py`

Handles both `"gemini"` and `"vertex"` provider names (same google-genai SDK, different auth):

- Constructor accepts `client` (pre-built `genai.Client`) and `provider_name` (`"gemini"` or `"vertex"`) in addition to `model_name`.
- `generate()`: calls `client.models.generate_content_stream(...)` (streaming to avoid idle timeouts), assembles full text; raises `AIRateLimitError` on resource-exhausted errors; handles `MALFORMED_FUNCTION_CALL` ValueError via `_handle_malformed_func_call_error` (copy helper from `service.py`).
- `stream()`: same streaming path, yields chunks.

#### NEW `core/ai/providers/anthropic.py`

Move logic from `service.py:_try_complete (provider=="anthropic")`:

- `generate()`: calls `client.messages.stream(...)` (streaming), assembles text; raises `AIRateLimitError` on 429.
- `stream()`: yields from `stream.text_stream`.
- `max_tokens = 4096` as class constant.

#### NEW `core/ai/providers/ollama.py`

- Same as `openai.py` but with localhost guard in constructor: validates `self.client.base_url` is localhost (preserve the security check).
- `generate()` and `stream()` use OpenAI-compat client.

#### NEW `core/ai/providers/gh.py`

Move logic from `service.py:_try_complete (provider=="gh")`:

- `generate()`: calls `subprocess.run(["gh", "models", "run", self.model_name], input=combined_prompt, ...)`; handles rate-limit (raises `AIRateLimitError`), context limit (raises `AIConfigurationError`).
- `stream()`: GH CLI does not support streaming — yield the full `generate()` response as a single chunk.
- `supports_tools()`: returns `False`.

#### NEW `core/ai/providers/mock.py`

Move `MockProvider` from the old `providers.py` (used only in tests):

```python
class MockProvider(BaseProvider):
    async def generate(self, prompt, system_prompt=None, **kwargs) -> str:
        if kwargs.get("force_error"):
            raise AIRateLimitError("Mock rate limit")
        return "Mock response"

    async def stream(self, prompt, system_prompt=None, **kwargs):
        yield "Mock "
        yield "stream"
```

### Step 3: Update `service.py` to delegate via factory

#### MODIFY `core/ai/service.py`

**3a. Add import at top:**

```python
from agent.core.ai.providers import get_provider
```

**3b. Rewrite `_try_complete`** — replace the `if/elif` provider chain with factory delegation:

```python
# SEARCH (current):
    def _try_complete(self, provider, system_prompt, user_prompt, model=None, temperature=None, stop_sequences=None) -> str:
        model_used = model or self.models.get(provider)
        from agent.core.config import config as _cfg
        max_retries = max(3, _cfg.panel_num_retries)
        
        for attempt in range(max_retries):
            try:
                if provider in ("gemini", "vertex"):
                    ...  # ~40 lines of google-genai SDK code
                elif provider == "openai":
                    ...  # ~15 lines
                elif provider == "gh":
                    ...  # ~60 lines
                elif provider == "anthropic":
                    ...  # ~20 lines
                elif provider == "ollama":
                    ...  # ~20 lines
            except Exception as e:
                ...  # string-based retry/rate-limit logic

# REPLACE WITH:
    def _try_complete(
        self,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Dispatch a completion request to the named provider via the AIProvider factory."""
        import asyncio
        from agent.core.ai.protocols import AIRateLimitError, AIConnectionError
        from agent.core.config import config as _cfg

        model_used = model or self.models.get(provider)
        client = self.clients.get(provider)
        max_retries = max(3, _cfg.panel_num_retries)

        provider_instance = get_provider(provider, client=client, model_name=model_used)

        for attempt in range(max_retries):
            try:
                result = asyncio.run(
                    provider_instance.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        stop_sequences=stop_sequences,
                    )
                )
                return result
            except AIRateLimitError as e:
                rate_limit_max = _cfg.panel_num_retries
                if attempt < rate_limit_max - 1:
                    wait_time = min(5 * (2 ** attempt), 60)
                    console.print(
                        f"[yellow]⚠️ Rate limit ({provider}). Backoff retry "
                        f"{attempt+1}/{rate_limit_max} in {wait_time}s...[/yellow]"
                    )
                    logging.warning(
                        "Rate limit (%s). Backoff retry %d/%d in %ds",
                        provider, attempt + 1, rate_limit_max, wait_time,
                        extra={"provider": provider, "attempt": attempt},
                    )
                    time.sleep(wait_time)
                    continue
                raise
            except AIConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logging.warning(
                        "AI connection error (%s): %s. Retrying %d/%d in %ds",
                        provider, e, attempt + 1, max_retries, wait_time,
                        extra={"provider": provider, "attempt": attempt},
                    )
                    time.sleep(wait_time)
                    continue
                raise
        return ""
```

**3c. Rewrite `stream_complete`** — replace `if/elif` provider chain:

```python
# In stream_complete, replace the large if/elif block with:
import asyncio

provider_instance = get_provider(provider, client=self.clients.get(provider), model_name=model_used)

async def _collect_stream():
    async for chunk in provider_instance.stream(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        stop_sequences=stop_sequences,
    ):
        yield chunk

# Drive the async generator synchronously via an event loop bridge
loop = asyncio.new_event_loop()
try:
    gen = _collect_stream()
    while True:
        try:
            chunk = loop.run_until_complete(gen.__anext__())
            yield chunk
        except StopAsyncIteration:
            break
finally:
    loop.close()
```

> **Note:** If `asyncio.run()` usage conflicts with an existing event loop (e.g. within `stream_complete` which is a sync generator), use `asyncio.new_event_loop()` for isolation. Alternatively, apply `nest_asyncio` if the service is called from a Textual async context. Evaluate during implementation and add a note in the code.

### Step 4: Delete the old flat `providers.py`

#### DELETE `core/ai/providers.py`

After all imports are migrated and tests pass, delete the old flat file. The package directory at `core/ai/providers/` replaces it.

- Verify no remaining imports of `agent.core.ai.providers.OpenAIProvider` (use `grep -r "from agent.core.ai.providers import" .agent/src .agent/tests`).

### Step 5: Update `core/ai/__init__.py`

#### MODIFY `core/ai/__init__.py`

Add provider factory to the public API:

```python
# SEARCH:
from .service import AIService, ai_service
from .protocols import AIProvider, AIError, AIRateLimitError, AIConnectionError

__all__ = ["AIService", "ai_service", "AIProvider", "AIError", "AIRateLimitError", "AIConnectionError"]

# REPLACE:
from .service import AIService, ai_service
from .protocols import AIProvider, AIError, AIRateLimitError, AIConnectionError, AIConfigurationError
from .providers import get_provider

__all__ = [
    "AIService", "ai_service",
    "AIProvider", "AIError", "AIRateLimitError", "AIConnectionError", "AIConfigurationError",
    "get_provider",
]
```

### Step 6: Migrate and update tests

#### MODIFY `core/ai/tests/test_providers.py`

Update all imports from `agent.core.ai.providers` to `agent.core.ai.providers` (the package `__init__` re-exports `get_provider`) and update concrete class imports:

```python
# SEARCH:
from agent.core.ai.providers import (
    OpenAIProvider,
    VertexAIProvider,
    MockProvider,
    get_provider,
)

# REPLACE:
from agent.core.ai.providers import get_provider
from agent.core.ai.providers.openai import OpenAIProvider
from agent.core.ai.providers.vertex import VertexAIProvider
from agent.core.ai.providers.mock import MockProvider
```

Update `MockProvider` test instantiation — new signature: `MockProvider(client=None, model_name="mock")`.

#### NEW `core/ai/tests/test_openai_provider.py`

```python
"""Unit tests for OpenAIProvider."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from agent.core.ai.protocols import AIRateLimitError, AIConnectionError
from agent.core.ai.providers.openai import OpenAIProvider


def _make_provider(model_name="gpt-4o"):
    mock_client = MagicMock()
    return OpenAIProvider(client=mock_client, model_name=model_name)


def test_generate_returns_content():
    p = _make_provider()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hello"))]
    p.client.chat.completions.create.return_value = mock_resp
    result = asyncio.run(p.generate("prompt"))
    assert result == "hello"


def test_generate_raises_rate_limit_on_429():
    p = _make_provider()
    p.client.chat.completions.create.side_effect = Exception("429 Too Many Requests")
    with pytest.raises(AIRateLimitError):
        asyncio.run(p.generate("prompt"))


def test_stream_yields_chunks():
    p = _make_provider()
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="chunk"))]
    p.client.chat.completions.create.return_value = [mock_chunk]
    
    async def collect():
        return [c async for c in p.stream("prompt")]
    
    chunks = asyncio.run(collect())
    assert "chunk" in chunks


def test_supports_tools_true():
    p = _make_provider()
    assert p.supports_tools() is True
```

#### NEW `core/ai/tests/test_anthropic_provider.py`

Similar structure — mock `anthropic.Anthropic`, test `generate()` assembles streaming text, `stream()` yields text, raises `AIRateLimitError` on 429.

#### NEW `core/ai/tests/test_ollama_provider.py`

Similar to OpenAI tests; verify localhost guard raises `AIConfigurationError` if non-localhost host is configured.

#### NEW `core/ai/tests/test_gh_provider.py`

Mock `subprocess.run`. Test:
- Successful response: `returncode=0`, `stdout="Result"` → `generate()` returns `"Result"`.
- Rate limit: `"rate limit"` in stderr → raises `AIRateLimitError`.
- Context limit: `"too large"` in stderr → raises `AIConfigurationError`.
- Stream: yields exact output of `generate()`.

### Step 7: Verify LOC ceiling and circular imports

```bash
# Count LOC in providers package (excluding blanks and comments)
grep -v '^\s*#' .agent/src/agent/core/ai/providers/*.py | grep -v '^\s*$' | wc -l

# Verify no circular imports
python -c "import agent.cli"

# Run all AI tests
pytest .agent/tests/core/ai/ -v
```

### Step 8: Update CHANGELOG.md

Add entry:

```
## [Unreleased]
### Refactored
- INFRA-108: Decomposed `core/ai/providers.py` into `core/ai/providers/` package with
  per-provider modules (openai, vertex, anthropic, ollama, gh, mock). `AIService._try_complete`
  and `stream_complete` now delegate to `AIProvider` instances via the `get_provider()` factory.
  Rate-limit retry uses typed `AIRateLimitError` instead of string matching.
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/core/ai/test_providers.py -v` — factory + protocol compliance
- [ ] `pytest .agent/tests/core/ai/test_openai_provider.py -v` — OpenAI generate/stream/retry
- [ ] `pytest .agent/tests/core/ai/test_anthropic_provider.py -v` — Anthropic generate/stream/retry
- [ ] `pytest .agent/tests/core/ai/test_ollama_provider.py -v` — Ollama + localhost guard
- [ ] `pytest .agent/tests/core/ai/test_gh_provider.py -v` — GH CLI + rate-limit + context-limit
- [ ] `pytest .agent/tests/core/ai/test_vertex_provider.py -v` — Vertex/Gemini (existing, verify patch targets)
- [ ] `pytest .agent/tests/core/ai/test_service.py -v` — AIService fallback chain unaffected
- [ ] `pytest .agent/tests/core/ai/test_streaming.py -v` — streaming utilities unaffected
- [ ] `python -c "import agent.cli"` — no circular imports (AC-8)
- [ ] `grep -v '^\s*#' .agent/src/agent/core/ai/providers/*.py | grep -v '^\s*$' | wc -l` — LOC < 500 (AC-9)

### Manual Verification

- [ ] Run `agent chat` → verify conversation round-trip works with configured provider
- [ ] Run `agent ask "hello"` → verify single-shot completion returns valid response
- [ ] Force-set a provider via `agent set-provider openai` and confirm dispatch uses `OpenAIProvider`
- [ ] Confirm `python -c "from agent.core.ai import get_provider; p = get_provider('mock'); print(type(p))"` prints `MockProvider`

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated (Step 8)
- [ ] README.md updated if public API surface changed
- [ ] All new modules have module-level docstrings (ADR-041 §6)

### Observability

- [ ] All provider modules use `logging.getLogger(__name__)` with structured `extra=` dicts
- [ ] No PII in log messages (provider names, model names, attempt counts only)
- [ ] OTel spans in `service.py` preserved unchanged

### Testing

- [ ] All existing `tests/core/ai/` tests pass (AC-6)
- [ ] New per-provider unit tests added (AC-7)
- [ ] `python -c "import agent.cli"` succeeds (AC-8)
- [ ] Combined providers/ LOC < 500 (AC-9)

## Copyright

Copyright 2026 Justin Cook
