# STORY-ID: INFRA-125: Implement ADR-012 Retry and Backoff Utilities

## State

ACCEPTED

## Goal Description

Implement a standardized, configurable retry and backoff utility library to ensure system resiliency and consistent exception handling across the platform. This utility will adhere to ADR-012, providing exponential backoff with jitter and integrated observability (metrics and structured logging) to prevent cascading failures and provide clear insights into transient errors.

## Linked Journeys

- JRN-004: Resilient Service Communication

## Panel Review Findings

### @Architect
- The implementation follows ADR-012 by providing exponential backoff with jitter.
- The utility is placed in `agent.core.implement.retry` to align with existing infrastructure patterns (like `circuit_breaker.py`).
- The design supports both synchronous and asynchronous operations, which is crucial for a shared infrastructure library.

### @Qa
- The Test Strategy includes unit tests for mathematical accuracy of the backoff and jitter distribution.
- Integration tests will verify the interaction with retryable vs. non-retryable exceptions.
- Mocking `asyncio.sleep` and `time.sleep` will ensure tests are fast and deterministic.

### @Security
- Logs are designed to capture only metadata (exception type, attempt number) and never the payload or credentials, preventing PII/secret leakage.
- Jitter is included to prevent "thundering herd" attacks or accidental DDoS on downstream services.

### @Product
- Acceptance criteria are fully addressed: configurable parameters, exponential backoff, and negative test handling for non-retryable errors.
- The negligible performance overhead requirement is met by using standard library primitives and lightweight OpenTelemetry calls.

### @Observability
- Every retry attempt emits a metric (`retry_attempts_total`) and a structured log.
- Logs include `extra` dictionaries for better indexing in log management systems.

### @Docs
- Module, class, and function docstrings follow PEP-257.
- A README-style explanation is provided in the module docstring.

### @Compliance
- Full license headers are included.
- Data handling is minimal and contains no user PII.

### @Mobile
- Not applicable; this is a backend core infrastructure change.

### @Web
- Not applicable; this is a backend core infrastructure change.

### @Backend
- Strict typing is enforced using Python's `typing` module.
- The API is designed to be easily integrated into existing verification loops and service clients.

## Codebase Introspection

### Targeted File Contents (from source)

(No targeted files provided in context; new files will be created.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| .agent/src/agent/core/implement/tests/test_retry.py | N/A | Entire File | Create new unit tests for retry logic |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Standardized Observability | ADR-012 | Use OpenTelemetry and structured logging | Yes |
| Backoff Strategy | ADR-012 | Exponential with Jitter | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Ensure any existing ad-hoc retry logic in `.agent/src/agent/core/implement/verification_orchestrator.py` is flagged for future migration.

## Implementation Steps

### Step 1: Create the Retry and Backoff Utility

#### [NEW] .agent/src/agent/core/implement/retry.py

```python
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
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar, Union

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

class NonRetryableError(Exception):
    """Exception that indicates a retry should not be attempted."""
    pass

async def retry_async(
    func: Callable[..., Any],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args: Any,
    **kwargs: Any
) -> Any:
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

    Raises:
        Exception: The last exception encountered or a NonRetryableError.
    """
    attempt = 0
    current_delay = initial_delay

    while True:
        try:
            with tracer.start_as_current_span("retry_attempt") as span:
                span.set_attribute("attempt", attempt)
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
                        "attempt": attempt
                    }
                )
                raise

            # Calculate delay with jitter
            # ADR-012: delay * (1 + random.uniform(-jitter, jitter))
            jitter_val = current_delay * jitter
            actual_delay = current_delay + random.uniform(-jitter_val, jitter_val)

            logger.warning(
                "Transient error encountered, retrying",
                extra={
                    "attempt": attempt,
                    "delay": actual_delay,
                    "exception": type(e).__name__
                }
            )

            retry_counter.add(1, {"exception": type(e).__name__, "attempt": str(attempt)})

            await asyncio.sleep(actual_delay)
            current_delay *= multiplier

def retry_sync(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args: Any,
    **kwargs: Any
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

    Raises:
        Exception: The last exception encountered or a NonRetryableError.
    """
    attempt = 0
    current_delay = initial_delay

    while True:
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            if isinstance(e, NonRetryableError):
                raise

            attempt += 1
            if attempt > max_retries:
                logger.error(
                    "Max retries exceeded (sync)",
                    extra={
                        "max_retries": max_retries,
                        "exception": type(e).__name__
                    }
                )
                raise

            jitter_val = current_delay * jitter
            actual_delay = current_delay + random.uniform(-jitter_val, jitter_val)

            logger.warning(
                "Transient error encountered (sync), retrying",
                extra={
                    "attempt": attempt,
                    "delay": actual_delay,
                    "exception": type(e).__name__
                }
            )

            retry_counter.add(1, {"exception": type(e).__name__, "mode": "sync"})

            time.sleep(actual_delay)
            current_delay *= multiplier

def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for wrapping functions with retry logic.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        multiplier: Multiplier for exponential backoff.
        jitter: Jitter factor.
        retryable_exceptions: Tuple of exceptions to retry.

    Returns:
        A decorated function.
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await retry_async(
                    func, max_retries, initial_delay, multiplier, jitter, retryable_exceptions, *args, **kwargs
                )
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return retry_sync(
                    func, max_retries, initial_delay, multiplier, jitter, retryable_exceptions, *args, **kwargs
                )
            return wrapper
    return decorator
```

### Step 2: Implement Unit Tests for Retry Logic

#### [NEW] .agent/src/agent/core/implement/tests/test_retry.py

```python
"""
Unit tests for ADR-012 Retry and Backoff utilities.

Copyright 2026 Justin Cook
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agent.core.implement.retry import retry_async, retry_sync, with_retry, NonRetryableError

@pytest.mark.asyncio
async def test_retry_async_success():
    """Verify that a successful call returns immediately without retries."""
    mock_func = AsyncMock(return_value="success")
    result = await retry_async(mock_func)
    assert result == "success"
    assert mock_func.call_count == 1

@pytest.mark.asyncio
async def test_retry_async_eventual_success():
    """Verify that a function eventually succeeds after retries."""
    mock_func = AsyncMock()
    mock_func.side_effect = [ValueError("fail"), ValueError("fail"), "success"]

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        result = await retry_async(mock_func, max_retries=3, initial_delay=1.0)
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

@pytest.mark.asyncio
async def test_retry_async_max_retries_exceeded():
    """Verify that max retries are respected."""
    mock_func = AsyncMock(side_effect=ValueError("constant fail"))

    with patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(ValueError, match="constant fail"):
            await retry_async(mock_func, max_retries=2)
        assert mock_func.call_count == 3  # Initial call + 2 retries

@pytest.mark.asyncio
async def test_retry_async_non_retryable_exception():
    """Verify that non-retryable exceptions fail immediately."""
    mock_func = AsyncMock(side_effect=TypeError("not retryable"))

    with pytest.raises(TypeError):
        await retry_async(mock_func, retryable_exceptions=(ValueError,))
    assert mock_func.call_count == 1

def test_retry_sync_success():
    """Verify synchronous retry success."""
    mock_func = MagicMock(side_effect=[RuntimeError("fail"), "success"])

    with patch("time.sleep") as mock_sleep:
        result = retry_sync(mock_func, max_retries=1)
        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once()

def test_retry_decorator_async():
    """Verify the with_retry decorator on async functions."""
    @with_retry(max_retries=1)
    async def sample_async():
        sample_async.counter += 1
        if sample_async.counter == 1:
            raise ValueError("fail")
        return "ok"

    sample_async.counter = 0

    with patch("asyncio.sleep", AsyncMock()):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(sample_async())
        assert result == "ok"
        assert sample_async.counter == 2

@pytest.mark.asyncio
async def test_jitter_and_backoff_calculation():
    """Verify that the delay increases and includes jitter."""
    mock_func = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), "ok"])

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        # Fixed random for predictable jitter
        with patch("random.uniform", return_value=0.0):
            await retry_async(mock_func, max_retries=2, initial_delay=1.0, multiplier=2.0, jitter=0.1)

            # Check sleep calls: first delay 1.0, second delay 2.0
            assert mock_sleep.call_args_list[0][0][0] == 1.0
            assert mock_sleep.call_args_list[1][0][0] == 2.0
```

## Verification Plan

### Automated Tests
- [ ] Run the new unit tests:
  `pytest .agent/src/agent/core/implement/tests/test_retry.py`
  Expected: All tests pass, showing retry logic, jitter, and backoff work as intended.
- [ ] Run linter to ensure PEP-257 compliance:
  `agent lint .agent/src/agent/core/implement/retry.py`
  Expected: No linting errors.

### Manual Verification
- [ ] Verify observability in logs (simulated):
  Run a test script that triggers retries and check if `Transient error encountered` logs appear with the correct `extra` fields.
  `PYTHONPATH=.agent/src python -c "from agent.core.implement.retry import retry_sync; retry_sync(lambda: 1/0, max_retries=1)"`
  Expected: Log output shows warning with `attempt: 1` and `exception: ZeroDivisionError`.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with INFRA-125
- [ ] README.md updated (if applicable) - Utility docstrings serve as primary developer documentation.

### Observability
- [ ] Logs are structured and free of PII (Verified in `retry.py` implementation)
- [ ] New structured `extra=` dicts added if new logging added (Verified in `retry.py` implementation)

### Testing
- [ ] All existing tests pass
- [ ] New tests added for each new public interface (Async, Sync, and Decorator)

## Copyright

Copyright 2026 Justin Cook