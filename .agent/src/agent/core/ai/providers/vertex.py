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
"""Vertex AI / Gemini provider backend implementing the AIProvider protocol.

Responsible for dispatching generate/stream requests to the Google Gen AI SDK
(``google.genai``) using either Gemini API-key auth or Vertex AI ADC auth.
Both paths share this module since they use the same SDK client interface.
"""
from __future__ import annotations

import logging
import re
from typing import Any, AsyncGenerator, Optional

from agent.core.ai.protocols import AIConnectionError, AIRateLimitError
from agent.core.ai.providers.base import BaseProvider
from agent.core.ai.streaming import ai_retry

logger = logging.getLogger(__name__)


def _extract_malformed_func_call_text(error: ValueError) -> str:
    """Extract plain text from a MALFORMED_FUNCTION_CALL ValueError.

    The google-genai SDK raises this when the model emits a ReAct-style
    ``Action:`` block instead of a valid JSON tool call.  We capture the
    text so the caller can continue rather than raising.

    Args:
        error: The ``ValueError`` raised by the google-genai library.

    Returns:
        Extracted text content, or an empty string if not found.
    """
    error_str = str(error)
    match = re.search(r"MALFORMED_FUNCTION_CALL:\s*(.*)", error_str, re.DOTALL)
    if match:
        return match.group(1).strip()
    if "Action:" in error_str:
        parts = error_str.split("Action:", 1)
        if len(parts) > 1:
            return "Action:" + parts[1]
    return ""


class VertexAIProvider(BaseProvider):
    """Google Vertex AI / Gemini implementation of the AIProvider protocol.

    Accepts a pre-built ``genai.Client`` (injected by ``AIService.reload()``)
    so that credentials are validated once at service start rather than per
    request.  A fresh client is constructed per request when ``client`` is
    ``None``, matching the existing ``service.py`` pattern that avoids stale
    sockets.
    """

    @ai_retry()
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete response via the Google Gen AI streaming API.

        Uses ``generate_content_stream`` internally so the HTTP connection
        stays alive and avoids 60 s / 120 s idle-timeout drops.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` (float) and ``stop_sequences``
                (list of str).

        Returns:
            The full assembled response text, stripped of leading/trailing
            whitespace.

        Raises:
            AIRateLimitError: On resource-exhausted (429) errors.
            AIConnectionError: On network or connectivity failures.
        """
        from google.genai import types  # type: ignore[import]

        client = self.client
        if client is None:
            # Lazy client construction — preserves existing service.py behaviour
            # when the provider is used without a pre-injected client (e.g. tests).
            from agent.core.ai.service import AIService  # local import avoids circular

            client = AIService._build_genai_client("vertex")

        logger.debug(
            "VertexAI generate start",
            extra={"model": self.model_name},
        )

        gen_config_kwargs: dict = {
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        }
        if system_prompt:
            gen_config_kwargs["system_instruction"] = system_prompt
        if kwargs.get("temperature") is not None:
            gen_config_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
            gen_config_kwargs["stop_sequences"] = kwargs["stop_sequences"]

        config = types.GenerateContentConfig(**gen_config_kwargs)

        try:
            full_text = ""
            response_stream = client.models.generate_content_stream(
                model=self.model_name, contents=prompt, config=config
            )
            try:
                for chunk in response_stream:
                    if chunk.text:
                        full_text += chunk.text
            except ValueError as val_err:
                extracted = _extract_malformed_func_call_text(val_err)
                if extracted:
                    full_text += extracted
                else:
                    raise
            return full_text.strip()
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "resource exhausted" in exc_str or "rate" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "timeout", "network", "unavailable")):
                raise AIConnectionError(str(exc)) from exc
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a response chunk-by-chunk via the Google Gen AI API.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Supports ``temperature`` and ``stop_sequences``.

        Yields:
            Non-empty text chunks as they arrive.

        Raises:
            AIRateLimitError: On resource-exhausted (429) errors.
            AIConnectionError: On network failures.
        """
        from google.genai import types  # type: ignore[import]

        client = self.client
        if client is None:
            from agent.core.ai.service import AIService  # local import avoids circular

            client = AIService._build_genai_client("vertex")

        gen_config_kwargs: dict = {
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        }
        if system_prompt:
            gen_config_kwargs["system_instruction"] = system_prompt
        if kwargs.get("temperature") is not None:
            gen_config_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("stop_sequences"):
            gen_config_kwargs["stop_sequences"] = kwargs["stop_sequences"]

        config = types.GenerateContentConfig(**gen_config_kwargs)

        try:
            for chunk in client.models.generate_content_stream(
                model=self.model_name, contents=prompt, config=config
            ):
                if chunk.text:
                    yield chunk.text
        except ValueError as val_err:
            extracted = _extract_malformed_func_call_text(val_err)
            if extracted:
                yield extracted
        except Exception as exc:
            exc_str = str(exc).lower()
            if "429" in exc_str or "resource exhausted" in exc_str:
                raise AIRateLimitError(str(exc)) from exc
            if any(kw in exc_str for kw in ("connection", "timeout", "network")):
                raise AIConnectionError(str(exc)) from exc
            raise
