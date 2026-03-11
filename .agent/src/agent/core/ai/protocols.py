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

from typing import Protocol, runtime_checkable, AsyncGenerator, Optional, List, Dict, Any

class AIProviderError(Exception):
    """Base exception for all AI provider errors."""
    def __init__(self, message: str, provider: Optional[str] = None, raw_response: Optional[Any] = None, original_exception: Optional[Exception] = None):
        self.message = message
        self.provider = provider
        self.raw_response = raw_response
        self.original_exception = original_exception
        super().__init__(message)

class AIError(AIProviderError):
    """Deprecated: Base exception for all AI provider errors (use AIProviderError)."""
    pass

class AIConnectionError(AIProviderError):
    """Raised when there is a network or connectivity issue with the provider."""
    pass

class AIRateLimitError(AIProviderError):
    """Raised when the provider rate limits the request."""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

class AIConfigurationError(AIProviderError):
    """Raised when provider configuration is missing or invalid."""
    pass

class AIAuthenticationError(AIProviderError):
    """Raised when authentication with the provider fails."""
    pass

class AIInvalidRequestError(AIProviderError):
    """Raised when the request provided is invalid (e.g. malformed prompt)."""
    pass

@runtime_checkable
class AIProvider(Protocol):
    """Protocol defining the interface for AI model providers."""
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> str:
        """Generate a complete text response."""
        ...

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a text response chunk by chunk."""
        ...

    def supports_tools(self) -> bool:
        """Return True if the provider supports tool calling."""
        ...

    def get_models(self) -> List[str]:
        """Return a list of available model identifiers for this provider."""
        ...