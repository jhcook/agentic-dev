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

import functools
import asyncio
import logging
import random
from typing import TypeVar, Callable, Any, Awaitable, AsyncGenerator, Optional
from agent.core.ai.protocols import AIRateLimitError, AIConnectionError

logger = logging.getLogger(__name__)

T = TypeVar("T")

def ai_retry(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying AI provider calls with exponential backoff and jitter.
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Wrap an async AI call with retry/backoff logic."""
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            """Execute the wrapped function, retrying on rate limit or connection errors."""
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (AIRateLimitError, AIConnectionError) as e:
                    last_error = e
                    if attempt == max_retries:
                        break
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.1 * (2 * random.random() - 1)
                    final_delay = max(0, delay + jitter)
                    logger.warning(
                        "AI request failed (%s), retrying in %.2fs (attempt %d/%d)",
                        type(e).__name__,
                        final_delay,
                        attempt + 1,
                        max_retries,
                        extra={"attempt": attempt, "error": str(e)},
                    )
                    await asyncio.sleep(final_delay)
            raise last_error or RuntimeError("Retry loop exited without result or error")
        return wrapper
    return decorator


async def process_stream(
    generator: AsyncGenerator[str, None],
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    """Consume an async stream, optionally invoking a callback per chunk.

    Args:
        generator: The async generator yielding string chunks.
        on_chunk: Optional callback invoked for each non-empty chunk.

    Returns:
        The fully assembled response string.
    """
    parts: list[str] = []
    async for chunk in generator:
        if chunk:
            parts.append(chunk)
            if on_chunk:
                on_chunk(chunk)
    return "".join(parts)