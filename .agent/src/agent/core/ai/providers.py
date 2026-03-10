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

"""
Contains the dynamic provider registry, the factory pattern dispatch, and concrete backend implementations (e.g. Anthropic).
"""

import logging
from typing import Optional, List, Dict, Any, AsyncGenerator, Type
from agent.core.ai.protocols import AIProvider, AIRateLimitError, AIConnectionError, AIConfigurationError
from agent.core.ai.streaming import ai_retry

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

logger = logging.getLogger(__name__)

class BaseProvider:
    """Base class for provider implementations with common logic."""
    def __init__(self, model_name: str):
        self.model_name = model_name

    def supports_tools(self) -> bool:
        """Return whether this provider supports tool/function calling."""
        return False

    def get_models(self) -> List[str]:
        """Return the list of model identifiers supported by this provider."""
        return [self.model_name]

class OpenAIProvider(BaseProvider):
    """OpenAI implementation of AIProvider."""
    
    @ai_retry()
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a complete response using the OpenAI API (stub; full dispatch in INFRA-108)."""
        logger.debug("Generating response using OpenAI", extra={"model": self.model_name, "provider": "openai"})
        if tracer:
            with tracer.start_as_current_span("ai_provider.generate") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "openai")
                return f"[OpenAI {self.model_name}] Response to: {prompt[:20]}..."
        return f"[OpenAI {self.model_name}] Response to: {prompt[:20]}..."

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token using the OpenAI API (stub; full dispatch in INFRA-108)."""
        logger.debug("Streaming response using OpenAI", extra={"model": self.model_name, "provider": "openai"})
        chunks = ["This ", "is ", "a ", "streamed ", "OpenAI ", "response."]
        if tracer:
            with tracer.start_as_current_span("ai_provider.stream") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "openai")
                for chunk in chunks:
                    yield chunk
        else:
            for chunk in chunks:
                yield chunk

class VertexAIProvider(BaseProvider):
    """Vertex AI implementation of AIProvider."""
    
    @ai_retry()
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a complete response using the Vertex AI (Gemini) API (stub; full dispatch in INFRA-108)."""
        logger.debug("Generating response using VertexAI", extra={"model": self.model_name, "provider": "vertex"})
        if tracer:
            with tracer.start_as_current_span("ai_provider.generate") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "vertex")
                return f"[Vertex {self.model_name}] Response to: {prompt[:20]}..."
        return f"[Vertex {self.model_name}] Response to: {prompt[:20]}..."

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token using the Vertex AI API (stub; full dispatch in INFRA-108)."""
        logger.debug("Streaming response using VertexAI", extra={"model": self.model_name, "provider": "vertex"})
        if tracer:
            with tracer.start_as_current_span("ai_provider.stream") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "vertex")
                yield f"[Vertex {self.model_name}] Streamed response"
        else:
            yield f"[Vertex {self.model_name}] Streamed response"

class MockProvider(BaseProvider):
    """Mock provider for testing purposes."""
    
    @ai_retry()
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a mock response, optionally raising AIRateLimitError for testing."""
        if tracer:
            with tracer.start_as_current_span("ai_provider.generate") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "mock")
                if "force_error" in kwargs:
                    raise AIRateLimitError("Mock rate limit")
                return "Mock response"
        else:
            if "force_error" in kwargs:
                raise AIRateLimitError("Mock rate limit")
            return "Mock response"

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[str, None]:
        """Yield mock stream chunks for testing."""
        if tracer:
            with tracer.start_as_current_span("ai_provider.stream") as span:
                span.set_attribute("model_name", self.model_name)
                span.set_attribute("provider", "mock")
                yield "Mock "
                yield "stream"
        else:
            yield "Mock "
            yield "stream"

# Registry for providers
_PROVIDER_REGISTRY: Dict[str, Type[AIProvider]] = {
    "gpt-4": OpenAIProvider,
    "gpt-4o": OpenAIProvider,
    "gpt-3.5-turbo": OpenAIProvider,
    "gemini-1.5-pro": VertexAIProvider,
    "mock": MockProvider,
}

def get_provider(model_name: str) -> AIProvider:
    """
    Factory function to retrieve a provider instance for a given model.
    """
    # Simple prefix matching or direct lookup
    provider_cls = _PROVIDER_REGISTRY.get(model_name)
    
    if not provider_cls:
        if model_name.startswith("gpt-"):
            provider_cls = OpenAIProvider
        elif model_name.startswith("gemini-"):
            provider_cls = VertexAIProvider
        else:
            logger.warning("Unknown model, defaulting to OpenAI", extra={"model": model_name, "provider": "openai"})
            provider_cls = OpenAIProvider
            
    return provider_cls(model_name=model_name)