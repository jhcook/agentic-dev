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
"""Anthropic Claude provider backend implementing the AIProvider protocol.

Responsible for dispatching generate/stream requests to the Anthropic Messages
API and mapping SDK exceptions to typed AIProvider errors.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from agent.core.ai.protocols import AIConnectionError, AIRateLimitError
from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.streaming import ai_retry

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096


class AnthropicProvider(BaseProvider):
    """Anthropic Claude implementation of the AIProvider protocol.

    Wraps the ``anthropic.Anthropic`` SDK client.  Uses the streaming Messages
    API for both ``generate()`` and ``stream()`` to prevent idle-timeout drops
    on large contexts.
    """

    @ai_retry()
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete response via the Anthropic Messages (streaming) API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` (float) and ``stop_sequences``
                (list of str).

        Returns:
            The full assembled response text, stripped of whitespace.

        Raises:
            AIRateLimitError: On HTTP 429 / overloaded responses.
            AIConnectionError: On network or connectivity failures.
        """
        if self.client is None:
            raise AIConnectionError("Anthropic client is not initialised.")

        logger.debug(
            "Anthropic generate start",
            extra={"model": self.model_name},
        )

        stream_kwargs: dict = {
            "model": self.model_name,
            "max_tokens": _MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            stream_kwargs["system"] = system_prompt
        if kwargs.get("temperature") is not None:
            stream_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
            stream_kwargs["stop_sequences"] = kwargs["stop_sequences"]

        try:
            full_text = ""
            with self.client.messages.stream(**stream_kwargs) as stream:
                for text in stream.text_stream:
                    full_text += text
            return full_text.strip()
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "overloaded" in exc_str or "rate limit" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "timeout", "network")):
                raise AIConnectionError(str(exc)) from exc
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token via the Anthropic Messages API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` and ``stop_sequences``.

        Yields:
            Text chunks as they arrive from the API.

        Raises:
            AIRateLimitError: On HTTP 429.
            AIConnectionError: On network failures.
        """
        if self.client is None:
            raise AIConnectionError("Anthropic client is not initialised.")

        stream_kwargs: dict = {
            "model": self.model_name,
            "max_tokens": _MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            stream_kwargs["system"] = system_prompt
        if kwargs.get("temperature") is not None:
            stream_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
            stream_kwargs["stop_sequences"] = kwargs["stop_sequences"]

        try:
            with self.client.messages.stream(**stream_kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "overloaded" in exc_str or "rate limit" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "timeout", "network")):
                raise AIConnectionError(str(exc)) from exc
            raise
