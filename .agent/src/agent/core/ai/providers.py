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

import logging
from typing import Dict, Type, List, Optional, Any, AsyncGenerator

from agent.core.ai.protocols import AIProvider, AIError, AIRateLimitError, AIConnectionError

logger = logging.getLogger(__name__)

class OpenAIProvider(AIProvider):
    """Implementation for OpenAI (GPT models)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        # Logic extracted from service.py monolith
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate a complete response using the OpenAI API."""
        logger.debug("Generating with OpenAI", extra={"model": kwargs.get("model")})
        # Placeholder: real SDK dispatch logic extracted in INFRA-108
        return "OpenAI response"

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token using the OpenAI API."""
        logger.debug("Streaming with OpenAI", extra={"model": kwargs.get("model")})
        yield "OpenAI "
        yield "stream"

    def supports_tools(self) -> bool:
        """Return True as OpenAI supports function/tool calling."""
        return True

    def get_models(self) -> List[str]:
        """Return the list of OpenAI model identifiers supported by this provider."""        
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

class VertexAIProvider(AIProvider):
    """Implementation for Google Cloud Vertex AI (Gemini)."""
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate a complete response using the Vertex AI (Gemini) API."""
        logger.debug("Generating with VertexAI", extra={"model": kwargs.get("model")})
        return "Vertex response"

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token using the Vertex AI API."""
        yield "Vertex "
        yield "stream"

    def supports_tools(self) -> bool:
        """Return True as Vertex AI (Gemini) supports tool/function calling."""
        return True

    def get_models(self) -> List[str]:
        """Return the list of Vertex AI model identifiers supported by this provider."""
        return ["gemini-1.5-pro", "gemini-1.5-flash"]

class OllamaProvider(AIProvider):
    """Implementation for local Ollama instances."""
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate a complete response using a local Ollama instance."""
        return "Ollama response"

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token from a local Ollama instance."""
        yield "Ollama stream"

    def supports_tools(self) -> bool:
        """Return False as Ollama does not currently support tool/function calling."""
        return False

    def get_models(self) -> List[str]:
        """Return the list of Ollama model identifiers supported by this provider."""
        return ["llama3", "mistral"]

# Provider Registry
_REGISTRY: Dict[str, Type[AIProvider]] = {
    "openai": OpenAIProvider,
    "vertex": VertexAIProvider,
    "ollama": OllamaProvider,
}

# Model mapping (simplified for INFRA-100)
_MODEL_TO_PROVIDER = {
    "gpt-4o": "openai",
    "gpt-4-turbo": "openai",
    "gemini-1.5-pro": "vertex",
    "llama3": "ollama",
}

def get_provider(model_name: str) -> AIProvider:
    """Factory to return the appropriate provider based on model name."""
    provider_key = "openai" # Default
    for model_prefix, key in _MODEL_TO_PROVIDER.items():
        if model_name.startswith(model_prefix):
            provider_key = key
            break
            
    provider_cls = _REGISTRY.get(provider_key)
    if not provider_cls:
        raise AIError(f"No provider found for model: {model_name}")
    
    logger.debug("Resolved provider for model", extra={"model": model_name, "provider": provider_key})
    return provider_cls()