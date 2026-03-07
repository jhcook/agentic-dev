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
"""OpenAI provider backend implementing the AIProvider protocol.

Responsible for dispatching generate/stream requests to the OpenAI Chat
Completions API and mapping SDK exceptions to typed AIProvider errors.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, List, Optional

from agent.core.ai.protocols import AIConnectionError, AIProvider, AIRateLimitError
from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.streaming import ai_retry

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI implementation of the AIProvider protocol.

    Wraps the ``openai.OpenAI`` SDK client. Raises ``AIRateLimitError`` on
    HTTP 429 responses and ``AIConnectionError`` on network failures.
    """

    def supports_tools(self) -> bool:
        """Return True — OpenAI supports function/tool calling."""
        return True

    @ai_retry()
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete response using the OpenAI Chat Completions API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction prepended to the message list.
            **kwargs: Forwarded to ``chat.completions.create`` (e.g. ``temperature``,
                ``stop``).

        Returns:
            The assistant's response content as a stripped string.

        Raises:
            AIRateLimitError: When the API returns a 429 Too Many Requests error.
            AIConnectionError: On network or connection failures.
        """
        if self.client is None:
            raise AIConnectionError("OpenAI client is not initialised.")

        logger.debug(
            "OpenAI generate start",
            extra={"model": self.model_name},
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        create_kwargs: dict = {
            "model": self.model_name,
            "messages": messages,
        }
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            create_kwargs["temperature"] = kwargs["temperature"]
        if "stop_sequences" in kwargs and kwargs["stop_sequences"]:
            create_kwargs["stop"] = kwargs["stop_sequences"]

        try:
            response = self.client.chat.completions.create(**create_kwargs)
            if response.choices:
                return (response.choices[0].message.content or "").strip()
            return ""
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "rate limit" in exc_str or "too many requests" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(
                kw in exc_str
                for kw in ("connection", "network", "timeout", "remote", "eof")
            ):
                raise AIConnectionError(str(exc)) from exc
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token using the OpenAI Chat Completions API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Forwarded to ``chat.completions.create``.

        Yields:
            Text chunks as they arrive from the API.

        Raises:
            AIRateLimitError: On HTTP 429.
            AIConnectionError: On network failures.
        """
        if self.client is None:
            raise AIConnectionError("OpenAI client is not initialised.")

        logger.debug(
            "OpenAI stream start",
            extra={"model": self.model_name},
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        create_kwargs: dict = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            create_kwargs["temperature"] = kwargs["temperature"]
        if "stop_sequences" in kwargs and kwargs["stop_sequences"]:
            create_kwargs["stop"] = kwargs["stop_sequences"]

        try:
            response = self.client.chat.completions.create(**create_kwargs)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "rate limit" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "network", "timeout")):
                raise AIConnectionError(str(exc)) from exc
            raise

    def get_models(self) -> List[str]:
        """Return known GPT model identifiers for this provider."""
        return [self.model_name] if self.model_name else ["gpt-4o"]
