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

from typing import Protocol, runtime_checkable, AsyncGenerator, Optional, List, Any

class AIError(Exception):
    """Base exception for all AI-related errors."""
    pass

class AIConnectionError(AIError):
    """Raised when there is a connectivity issue with the AI provider."""
    pass

class AIRateLimitError(AIError):
    """Raised when the AI provider returns a rate limit error (e.g., HTTP 429)."""
    pass

class AIConfigurationError(AIError):
    """Raised when the AI provider is misconfigured or missing credentials."""
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
        """Generate a single text completion."""
        ...

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a text completion as an async generator of chunks."""
        yield ""

    def supports_tools(self) -> bool:
        """Returns True if the provider supports tool/function calling."""
        ...

    def get_models(self) -> List[str]:
        """Returns a list of supported model identifiers for this provider."""
        ...