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
"""Ollama local provider backend implementing the AIProvider protocol.

Responsible for dispatching generate/stream requests to a localhost Ollama
instance via the OpenAI-compatible REST API, with a security guard preventing
use against remote hosts.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse

from agent.core.ai.protocols import AIConfigurationError, AIConnectionError, AIRateLimitError
from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.streaming import ai_retry

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama (local) implementation of the AIProvider protocol.

    Uses the OpenAI-compatible ``/v1/chat/completions`` endpoint exposed by
    Ollama.  Enforces a localhost-only security guard to prevent accidental
    data exfiltration to remote Ollama hosts.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """Initialise the Ollama provider with a localhost security check.

        Args:
            client: Pre-built OpenAI-SDK-compat client pointing at the Ollama
                ``/v1`` base URL.
            model_name: Default model identifier (e.g. ``"llama3"``).

        Raises:
            AIConfigurationError: If ``client.base_url`` points to a non-localhost
                host, preventing accidental data exfiltration.
        """
        super().__init__(client=client, model_name=model_name)

        # @Security: Guard against remote Ollama hosts (data exfiltration risk)
        if client is not None:
            base_url = str(getattr(client, "base_url", "") or "")
            parsed = urlparse(base_url)
            hostname = parsed.hostname or ""
            if hostname and hostname not in ("localhost", "127.0.0.1", "::1", ""):
                raise AIConfigurationError(
                    f"OLLAMA_HOST ({base_url!r}) is not localhost — "
                    "remote Ollama hosts are blocked for security."
                )

    @ai_retry()
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete response via the Ollama OpenAI-compat API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` and ``stop_sequences``.

        Returns:
            The assistant's response text, stripped of whitespace.

        Raises:
            AIRateLimitError: On rate-limit responses.
            AIConnectionError: When Ollama is unreachable.
        """
        if self.client is None:
            raise AIConnectionError("Ollama client is not initialised.")

        logger.debug(
            "Ollama generate start",
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
        if kwargs.get("temperature") is not None:
            create_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
            create_kwargs["stop"] = kwargs["stop_sequences"]

        try:
            response = self.client.chat.completions.create(**create_kwargs)
            if response.choices:
                content = response.choices[0].message.content
                return (content or "").strip()
            return ""
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "rate limit" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "timeout", "network", "refused")):
                raise AIConnectionError(str(exc)) from exc
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a response via the Ollama OpenAI-compat API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` and ``stop_sequences``.

        Yields:
            Text chunks as they arrive.

        Raises:
            AIRateLimitError: On rate-limit responses.
            AIConnectionError: When Ollama is unreachable.
        """
        if self.client is None:
            raise AIConnectionError("Ollama client is not initialised.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        create_kwargs: dict = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        if kwargs.get("temperature") is not None:
            create_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
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
            if any(kw in exc_str for kw in ("connection", "timeout", "network", "refused")):
                raise AIConnectionError(str(exc)) from exc
            raise
