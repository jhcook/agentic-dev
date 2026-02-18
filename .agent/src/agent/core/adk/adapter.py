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

"""
AIService ↔ ADK Bridge Adapter.

Wraps the synchronous AIService.complete() behind ADK's BaseLlm interface
so that ADK agents can use any provider configured in the CLI (Gemini,
OpenAI, Anthropic, GitHub CLI) without knowing about them directly.

Design decisions:
  - Uses asyncio.run_in_executor() to bridge sync → async.
  - Uses threading.Lock() because AIService is a global singleton.
  - Caps output at 50 000 chars to protect against runaway responses.
"""

import asyncio
import threading
import logging
from typing import AsyncGenerator

from google.genai import types
from google.adk.models import BaseLlm, LlmRequest, LlmResponse

from agent.core.ai import ai_service

logger = logging.getLogger(__name__)


class AIServiceModelAdapter(BaseLlm):
    """Adapts the synchronous AIService to ADK's async BaseLlm interface.

    Thread-safe: a threading.Lock guards the underlying singleton so
    concurrent agent calls do not interleave provider state.
    """

    def __init__(self):
        self._ai_service = ai_service
        self._lock = threading.Lock()

    # ---- Sync bridge ----

    def _sync_complete(self, system_prompt: str, user_prompt: str) -> str:
        """Thread-safe synchronous completion via AIService."""
        with self._lock:
            result = self._ai_service.complete(system_prompt, user_prompt)
        return (result or "")[:50_000]

    # ---- ADK interface ----

    async def generate_content_async(
        self, llm_request: LlmRequest, **kwargs
    ) -> LlmResponse:
        """ADK calls this method for non-streaming completions.

        Extracts system + user prompts from the LlmRequest, runs through
        AIService.complete() in a thread pool, and wraps the result.
        """
        system_prompt = ""
        if llm_request.config and llm_request.config.system_instruction:
            si = llm_request.config.system_instruction
            if isinstance(si, str):
                system_prompt = si
            elif hasattr(si, "parts"):
                system_prompt = "\n".join(
                    p.text for p in si.parts if hasattr(p, "text")
                )

        user_prompt = ""
        if llm_request.contents:
            parts = []
            for msg in llm_request.contents:
                if hasattr(msg, "parts"):
                    for part in msg.parts:
                        if hasattr(part, "text") and part.text:
                            parts.append(part.text)
            user_prompt = "\n".join(parts)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,  # Default thread pool
            self._sync_complete,
            system_prompt,
            user_prompt,
        )

        logger.debug(
            "AIServiceModelAdapter: completed (system=%d chars, user=%d chars, result=%d chars)",
            len(system_prompt), len(user_prompt), len(result),
        )

        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=result)],
            )
        )

    async def generate_content_async_stream(
        self, llm_request: LlmRequest, **kwargs
    ) -> AsyncGenerator[LlmResponse, None]:
        """Streaming variant — delegates to non-streaming since AIService
        does not support streaming."""
        response = await self.generate_content_async(llm_request, **kwargs)
        yield response
