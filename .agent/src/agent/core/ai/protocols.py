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

class AIError(Exception):
    """Base exception for all AI provider errors."""
    pass

class AIConnectionError(AIError):
    """Raised when there is a network or connectivity issue with the provider."""
    pass

class AIRateLimitError(AIError):
    """Raised when the provider rate limits the request."""
    pass

class AIConfigurationError(AIError):
    """Raised when provider configuration is missing or invalid."""
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