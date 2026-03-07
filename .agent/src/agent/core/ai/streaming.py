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

import asyncio
import functools
import logging
from typing import Callable, Any, TypeVar, AsyncGenerator, Optional

from agent.core.ai.protocols import AIRateLimitError, AIConnectionError

logger = logging.getLogger(__name__)

T = TypeVar("T")

def ai_retry(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying AI provider calls with exponential backoff.
    Specifically handles rate limits and connection issues.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap an async AI call with retry/backoff logic."""
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Execute the wrapped function, retrying on rate limit or connection errors."""
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except AIRateLimitError as e:
                    last_exception = e
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Rate limited by AI provider, retrying in %.1fs", 
                        delay, 
                        extra={"attempt": attempt + 1, "max_retries": max_retries}
                    )
                    await asyncio.sleep(delay)
                except AIConnectionError as e:
                    last_exception = e
                    delay = base_delay * 0.5  # Faster retry for connection blips
                    logger.debug(
                        "Connection issue with AI provider, retrying in %.1fs", 
                        delay, 
                        extra={"attempt": attempt + 1}
                    )
                    await asyncio.sleep(delay)
            
            if last_exception:
                raise last_exception
            raise AIRateLimitError("Max retries exceeded")
        return wrapper
    return decorator

async def process_stream(
    generator: AsyncGenerator[str, None], 
    on_chunk: Optional[Callable[[str], None]] = None
) -> str:
    """
    Helper to consume an async stream, optionally calling a callback per chunk,
    and returning the fully assembled string.
    """
    full_response = []
    async for chunk in generator:
        if chunk:
            full_response.append(chunk)
            if on_chunk:
                on_chunk(chunk)
    return "".join(full_response)