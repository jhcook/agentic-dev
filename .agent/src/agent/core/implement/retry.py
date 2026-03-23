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

"""Retry logic with exponential backoff and jitter (INFRA-169)."""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Type, Union, Tuple

logger = logging.getLogger(__name__)

class MaxRetriesExceededError(Exception):
    """Raised when an operation fails after all retry attempts are exhausted."""
    pass

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
):
    """
    Decorator for async functions to apply exponential backoff and jitter.
    
    Args:
        max_retries: Number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        backoff_factor: Multiplier for the delay after each failure.
        jitter: If True, adds random jitter to the delay.
        exceptions: The exception class or tuple of classes to catch and retry.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            "chunk_retry_failed_permanently func=%s attempts=%d error=%s",
                            func.__qualname__, attempt - 1, str(e)
                        )
                        raise MaxRetriesExceededError(
                            f"Chunk task '{func.__name__}' failed after {max_retries} attempts."
                        ) from e
                    
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        "chunk_retry_attempt func=%s attempt=%d/%d delay=%.2fs error=%s",
                        func.__qualname__, attempt, max_retries, delay, str(e)
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
