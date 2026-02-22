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

Wraps the synchronous AIService._try_complete() behind ADK's BaseLlm
interface so that ADK agents can use the configured provider (Gemini,
OpenAI, Anthropic, GitHub CLI) without knowing about them directly.

Design decisions:
  - Uses asyncio.run_in_executor() to bridge sync → async.
  - Calls _try_complete() directly instead of complete() to avoid
    mutating shared provider-fallback state on the singleton.  This
    makes concurrent agent execution (via asyncio.gather) safe.
  - Caps output at 50 000 chars to protect against runaway responses.
"""

import asyncio
import logging
import threading
from typing import AsyncGenerator

from google.genai import types
from google.adk.models import BaseLlm, LlmRequest, LlmResponse

from agent.core.ai import ai_service

logger = logging.getLogger(__name__)

# Limit concurrent API calls to avoid overwhelming the provider.
# Uses a threading.Semaphore (not asyncio.Semaphore) because the actual
# blocking happens in threads via asyncio.to_thread().
_MAX_CONCURRENT_API_CALLS = 3
_thread_semaphore = threading.Semaphore(_MAX_CONCURRENT_API_CALLS)


class AIServiceModelAdapter(BaseLlm):
    """Adapts the synchronous AIService to ADK's async BaseLlm interface.

    Thread-safe for concurrent usage: calls _try_complete() directly
    with the configured provider, avoiding shared fallback state.

    Uses asyncio.to_thread() (not loop.run_in_executor) because the
    latter deadlocks when ADK's InMemoryRunner consumes the async
    generator — the runner's internal event-loop consumption pattern
    prevents the executor future from resolving.
    """

    def __init__(self):
        # BaseLlm is Pydantic and requires `model: str`.
        # Pull the configured model name from ai_service / config.
        from agent.core.config import config
        # We don't know the provider until _sync_complete looks at ai_service,
        # but BaseLlm requires a string model immediately on init.
        # Delay true model resolution until the API call.
        super().__init__(model="dynamic-resolution")
        self._ai_service = ai_service

    # ---- Sync bridge (runs in thread via asyncio.to_thread) ----

    def _sync_complete(self, system_prompt: str, user_prompt: str) -> str:
        """Synchronous completion via AIService._try_complete().

        Bypasses the outer complete() fallback chain so concurrent
        agents don't race on shared provider state.  Rate-limit
        retries with exponential backoff are handled inside
        _try_complete() itself.

        Acquires a threading.Semaphore to cap concurrent API calls.
        """
        with _thread_semaphore:
            self._ai_service._ensure_initialized()
            provider = self._ai_service.provider or "gemini"
            
            # Use the configured model if specified in agent.yaml
            from agent.core.config import config
            configured_model = config.get_model(provider)
            
            result = self._ai_service._try_complete(
                provider, system_prompt, user_prompt, configured_model
            )
        return (result or "")[:50_000]

    # ---- ADK interface ----

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """ADK calls this as an async generator.

        Extracts system + user prompts from the LlmRequest, runs through
        AIService._try_complete() in a separate thread, and yields the result.
        Since AIService does not support streaming, yields a single response.

        Uses asyncio.to_thread() instead of loop.run_in_executor() to avoid
        deadlocking inside ADK's InMemoryRunner async generator consumption.
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

        result = await asyncio.to_thread(
            self._sync_complete,
            system_prompt,
            user_prompt,
        )

        logger.debug(
            "AIServiceModelAdapter: completed (system=%d chars, user=%d chars, result=%d chars)",
            len(system_prompt), len(user_prompt), len(result),
        )

        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=result)],
            )
        )
