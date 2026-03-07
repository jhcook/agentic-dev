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
"""GitHub CLI (gh models) provider backend implementing the AIProvider protocol.

Responsible for dispatching generate requests to the GitHub Models service via
the ``gh models run`` subprocess command, mapping exit-code / stderr patterns
to typed AIProvider errors.  Streaming is not supported by the GH CLI; the
``stream()`` method yields the full ``generate()`` response as a single chunk.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any, AsyncGenerator, List, Optional

from agent.core.ai.protocols import AIConfigurationError, AIRateLimitError
from agent.core.ai.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GHProvider(BaseProvider):
    """GitHub CLI (gh models) implementation of the AIProvider protocol.

    Executes ``gh models run <model>`` as a subprocess and maps well-known
    stderr patterns to typed errors.  The GH CLI does not support streaming;
    ``stream()`` yields the complete response as a single chunk.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response via the ``gh models run`` CLI command.

        Combines the system prompt and user prompt into a single stdin payload
        to avoid ARG_MAX limits on long inputs.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction, prepended to the prompt.
            **kwargs: Unused; accepted for protocol compatibility.

        Returns:
            The stripped stdout of the ``gh models run`` invocation.

        Raises:
            AIRateLimitError: When GH API rate-limits the request.
            AIConfigurationError: On context-length exceeded (413 / "too large").
        """
        model = self.model_name

        combined = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
        logger.debug(
            "GH CLI generate start",
            extra={"model": model},
        )

        result = subprocess.run(
            ["gh", "models", "run", model],
            input=combined,
            text=True,
            capture_output=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

        err = result.stderr.lower()

        # Context / payload limit — do not retry
        if "too large" in err or "413" in err or "context length" in err:
            logger.error(
                "GH context limit exceeded",
                extra={"model": model, "stderr": result.stderr[:200]},
            )
            raise AIConfigurationError(
                "GH Models context limit exceeded.  Use Gemini or OpenAI for large prompts."
            )

        # Rate limiting — caller's retry decorator will handle backoff
        if "rate limit" in err or "too many requests" in err:
            raise AIRateLimitError(f"GH rate limit: {result.stderr.strip()}")

        # Generic failure
        logger.error(
            "GH CLI error",
            extra={"model": model, "stderr": result.stderr[:200]},
        )
        raise RuntimeError(f"GH CLI error: {result.stderr.strip()}")

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Yield the complete generate() response as a single chunk.

        The ``gh models run`` CLI does not support streaming output.  This
        method provides protocol compatibility by collecting the full response
        and yielding it once.

        Args:
            prompt: The user message content.
            system_prompt: Optional system instruction.
            **kwargs: Forwarded to ``generate()``.

        Yields:
            The complete response as a single string chunk.
        """
        result = await self.generate(prompt, system_prompt=system_prompt, **kwargs)
        if result:
            yield result

    def get_models(self) -> List[str]:
        """Return the configured GH Models model identifier."""
        return [self.model_name] if self.model_name else ["openai/gpt-4o"]
