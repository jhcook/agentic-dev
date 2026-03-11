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

import pytest
from typing import Optional, AsyncGenerator

from agent.core.ai.protocols import (
    AIProvider,
    AIProviderError,
    AIError,
    AIConnectionError,
    AIRateLimitError,
    AIConfigurationError,
    AIAuthenticationError,
    AIInvalidRequestError,
)
from agent.core.ai.providers.utils import scrub_pii, format_provider_error

def test_exception_hierarchy():
    # Base class should take message and provider
    err = AIProviderError("test message", provider="test_provider")
    assert err.message == "test message"
    assert err.provider == "test_provider"
    assert str(err) == "test message"

    # Legacy subclass should still match base
    legacy_err = AIError("legacy error")
    assert isinstance(legacy_err, AIProviderError)

    rate_limit = AIRateLimitError("rate limited", retry_after=60)
    assert rate_limit.retry_after == 60
    assert isinstance(rate_limit, AIProviderError)

    auth_err = AIAuthenticationError("auth failed")
    assert isinstance(auth_err, AIProviderError)

def test_runtime_checkable():
    class DummyProvider:
        async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
            return ""
        async def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
            yield ""
        def supports_tools(self) -> bool:
            return False
        def get_models(self) -> list[str]:
            return []

    dummy = DummyProvider()
    assert isinstance(dummy, AIProvider)

def test_scrub_pii():
    text = "Contact john.doe@example.com or use api_key: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
    scrubbed = scrub_pii(text)
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed
    assert "john.doe" not in scrubbed

def test_format_provider_error():
    formatted = format_provider_error("Something went wrong", "openai")
    assert formatted == "[openai] Something went wrong"
