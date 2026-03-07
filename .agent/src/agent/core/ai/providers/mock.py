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
"""Mock provider backend for use in tests.

Responsible for providing deterministic, dependency-free AIProvider responses
so unit tests can verify dispatch logic without requiring real SDK clients.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

from agent.core.ai.protocols import AIRateLimitError
from agent.core.ai.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic mock implementation of the AIProvider protocol.

    Returns fixed responses by default.  Pass ``force_error=True`` in kwargs
    to ``generate()`` to trigger an ``AIRateLimitError`` for retry-logic tests.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Return a fixed mock response, or raise AIRateLimitError if requested.

        Args:
            prompt: Ignored.
            system_prompt: Ignored.
            **kwargs: Pass ``force_error=True`` to raise ``AIRateLimitError``.

        Returns:
            ``"Mock response"`` string.

        Raises:
            AIRateLimitError: When ``force_error=True`` is in kwargs.
        """
        if kwargs.get("force_error"):
            raise AIRateLimitError("Mock rate limit")
        return "Mock response"

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Yield fixed mock stream chunks.

        Args:
            prompt: Ignored.
            system_prompt: Ignored.
            **kwargs: Unused.

        Yields:
            ``"Mock "`` then ``"stream"``.
        """
        yield "Mock "
        yield "stream"
