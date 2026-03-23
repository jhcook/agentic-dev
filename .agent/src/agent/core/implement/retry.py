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
Standardized Retry and Backoff Utilities.

This module implements ADR-012, providing exponential backoff with jitter
and integrated observability for both synchronous and asynchronous operations.

Copyright 2026 Justin Cook
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
"""

import asyncio
import functools
import random
import time
from typing import (
    Any, 
    Callable, 
    Dict, 
    Optional, 
    Tuple, 
    Type, 
    TypeVar, 
    Union, 
    Awaitable, 
    ParamSpec,
    overload
)

from opentelemetry import metrics, trace
from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics definition
retry_counter = meter.create_counter(
    "retry_attempts_total",
    description="Total number of retry attempts made",
    unit="1",
)

T = TypeVar("T")
P = ParamSpec("P")

class NonRetryableError(Exception):
    """Exception that indicates a retry should not be attempted."""
    pass

async def retry_async(
    func: Callable[P, Awaitable[T]],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """
    Execute an async function with exponential backoff and jitter.

    Args:
        func: The async function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        multiplier: Multiplier for exponential backoff.
        jitter: Jitter factor (fraction of delay).
        retryable_exceptions: Tuple of exception types to retry on.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        The result of the function call.
    """
    attempt = 0
    current_delay = initial_delay

    while True:
        try:
            with tracer.start_as_current_span("retry_attempt") as span:
                span.set_attribute("attempt", attempt)
                span.set_attribute("mode", "async")
                return await func(*args, **kwargs)
        except retryable_exceptions as e:
            if isinstance(e, NonRetryableError):
                raise

            attempt += 1
            if attempt > max_retries:
                logger.error(
                    "Max retries exceeded",
                    extra={
                        "max_retries": max_retries,
                        "exception": type(e).__name__,
                        "attempt": attempt,
                        "mode": "async"
                    }
                )
                raise

            jitter_val = current_delay * jitter
            actual_delay = current_delay + random.uniform(-jitter_val, jitter_val)

            logger.warning(
                "Transient error encountered, retrying",
                extra={
                    "attempt": attempt,
                    "delay": actual_delay,
                    "exception": type(e).__name__,
                    "mode": "async"
                }
            )

            # Metric attributes standardized (low cardinality)
            retry_counter.add(1, {"exception": type(e).__name__, "mode": "async"})

            await asyncio.sleep(actual_delay)
            current_delay *= multiplier

def retry_sync(
    func: Callable[P, T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """
    Execute a synchronous function with exponential backoff and jitter.

    Args:
        func: The function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        multiplier: Multiplier for exponential backoff.
        jitter: Jitter factor (fraction of delay).
        retryable_exceptions: Tuple of exception types to retry on.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        The result of the function call.
    """
    attempt = 0
    current_delay = initial_delay

    while True:
        try:
            with tracer.start_as_current_span("retry_attempt") as span:
                span.set_attribute("attempt", attempt)
                span.set_attribute("mode", "sync")
                return func(*args, **kwargs)
        except retryable_exceptions as e:
            if isinstance(e, NonRetryableError):
                raise

            attempt += 1
            if attempt > max_retries:
                logger.error(
                    "Max retries exceeded",
                    extra={
                        "max_retries": max_retries,
                        "exception": type(e).__name__,
                        "attempt": attempt,
                        "mode": "sync"
                    }
                )
                raise

            jitter_val = current_delay * jitter
            actual_delay = current_delay + random.uniform(-jitter_val, jitter_val)

            logger.warning(
                "Transient error encountered, retrying",
                extra={
                    "attempt": attempt,
                    "delay": actual_delay,
                    "exception": type(e).__name__,
                    "mode": "sync"
                }
            )

            retry_counter.add(1, {"exception": type(e).__name__, "mode": "sync"})

            time.sleep(actual_delay)
            current_delay *= multiplier

@overload
def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Overload for async functions."""
    ...

@overload
def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Overload for sync functions."""
    ...

def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    Decorator for wrapping functions with retry logic, preserving signatures.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        multiplier: Multiplier for exponential backoff.
        jitter: Jitter factor (fraction of delay).
        retryable_exceptions: Tuple of exception types to retry on.

    Returns:
        The decorated function.
    """
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        """Wrap the function with retry logic."""
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                """Async wrapper function."""
                return await retry_async(
                    func, max_retries, initial_delay, multiplier, jitter, retryable_exceptions, *args, **kwargs
                )
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                """Sync wrapper function."""
                return retry_sync(
                    func, max_retries, initial_delay, multiplier, jitter, retryable_exceptions, *args, **kwargs
                )
            return wrapper
    return decorator


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
        @functools.wraps(func)
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
                            f"Failed after {attempt - 1} retries: {e}"
                        ) from e

                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "chunk_retry func=%s attempt=%d/%d delay=%.2fs error=%s",
                        func.__qualname__, attempt, max_retries, delay, str(e),
                    )
                    retry_counter.add(
                        1, {"exception": type(e).__name__, "mode": "async_backoff"}
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator