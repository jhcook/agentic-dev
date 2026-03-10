# AI Providers Architecture Guide

## Overview

The `AIService` utilizes a modular `AIProvider` architecture to interface with different LLM backends (OpenAI, Vertex, etc.). This Strategy pattern prevents the `AIService` facade from becoming a monolith as we support additional models, while preserving a unified API interface for older code paths.

## The `AIProvider` Protocol

All providers must implement the `AIProvider` Protocol defined in `src/agent/core/ai/protocols.py`. This ensures runtime duck-typing safety via `@runtime_checkable`.

```python
from typing import Protocol, runtime_checkable, AsyncGenerator, Optional, List

@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str: ...
    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]: ...
    def supports_tools(self) -> bool: ...
    def get_models(self) -> List[str]: ...
```

## Adding a New Provider

To add a new AI provider, follow these 3 steps:

### 1. Create the Provider Class
In `src/agent/core/ai/providers.py` (or a dedicated file under `src/agent/core/ai/providers/` according to standard decomposition rules), create a class that inherits from `BaseProvider` and implements the `AIProvider` Protocol.

```python
from agent.core.ai.providers import BaseProvider
from agent.core.ai.streaming import ai_retry

class MyNewProvider(BaseProvider):
    @ai_retry()
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Implementing custom API calls...
        pass

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        # Implementing generator streams...
        pass
```

### 2. Standardize Errors
A provider must catch any SDK-specific HTTP errors (like `openai.RateLimitError`) and raise the canonical exceptions defined in `protocols.py` such as `AIRateLimitError` or `AIConnectionError`. This ensures the `ai_retry` decorators and circuit breakers behave agnostically.

### 3. Register the Provider
If appending to `providers.py`, place your class in the module and map it under the `_PROVIDER_REGISTRY` dict at the bottom of the file.

```python
_PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "vertex": VertexAIProvider,
    "mynew": MyNewProvider
}
```

## Observability & Tracing

When implementing your custom provider's `generate/stream` endpoints, remember to integrate the `tracer` from `opentelemetry` to map your model metrics effectively.

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

class MyNewProvider(BaseProvider):
    # Inside generate()...
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if tracer:
            with tracer.start_as_current_span("ai_provider.generate") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "mynew")
                # Do the generation
```


## Copyright

Copyright 2026 Justin Cook
