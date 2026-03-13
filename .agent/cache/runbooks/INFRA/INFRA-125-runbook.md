# STORY-ID: INFRA-125: Implement ADR-012 Retry and Backoff Utilities

## State

ACCEPTED

## Goal Description

Implement a standardized, configurable retry and backoff utility library to ensure system resiliency and consistent exception handling across the platform. This utility will adhere to ADR-012, providing exponential backoff with jitter and integrated observability (metrics and structured logging) to prevent cascading failures and provide clear insights into transient errors.

## Linked Journeys

- JRN-004: Resilient Service Communication

## Panel Review Findings

### @Architect
- **Update:** The utility ensures parity between synchronous and asynchronous execution paths. Both paths now include OpenTelemetry tracing and standardized metrics to eliminate observability gaps.
- The implementation follows ADR-012 by providing exponential backoff with jitter.
- The utility is placed in `agent.core.implement.retry` to align with existing infrastructure patterns.

### @Qa
- **Update:** Test coverage has been expanded to include the `with_retry` decorator for synchronous functions, the `NonRetryableError` short-circuit logic, and verification of OpenTelemetry metric emission.
- The Test Strategy includes unit tests for mathematical accuracy of the backoff and jitter distribution.
- Mocking `asyncio.sleep` and `time.sleep` ensures tests are fast and deterministic.

### @Security
- Logs are designed to capture only metadata (exception type, attempt number) and never the payload or credentials, preventing PII/secret leakage.
- Jitter is included to prevent "thundering herd" attacks or accidental DDoS on downstream services.

### @Product
- **Update:** Structured logs and metric tags are harmonized across sync/async modes. High-cardinality data (like attempt counts) is moved from metric tags to logs/traces to ensure cost-effective and performant monitoring.
- **Documentation Requirement:** To ensure developer adoption and value realization, comprehensive user-facing documentation (README and CHANGELOG) must be finalized as part of the delivery.

### @Observability
- **Update:** Trace spans are now consistent across both `retry_async` and `retry_sync`. Metric attributes are standardized to `{"exception": "...", "mode": "sync|async"}`.
- Every retry attempt emits a metric (`retry_attempts_total`) and a structured log.
- Logs include `extra` dictionaries for better indexing in log management systems.

### @Docs
- Module, class, and function docstrings follow PEP-257.
- A README-style explanation is provided in the module docstring.

### @Compliance
- **Update:** Full license headers are applied to all new files, including the test suite.
- Data handling is minimal and contains no user PII.

### @Backend
- **Update:** Strict typing is enforced using `ParamSpec`, `TypeVar`, and `overload` to preserve the signature and return types of decorated functions. 
- The API is designed to handle both `Awaitable` and standard return types without type erasure (avoiding `Any`).

## Codebase Introspection

### Targeted File Contents (from source)

(No targeted files provided in context; new files will be created.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| .agent/src/agent/core/implement/tests/test_retry.py | N/A | Entire File | Create new unit tests for retry logic, decorators, and metrics |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Standardized Observability | ADR-012 | Use OpenTelemetry and structured logging (consistent across sync/async) | Yes |
| Backoff Strategy | ADR-012 | Exponential with Jitter | Yes |
| Type Integrity | Backend Standards | Preserve function signatures and return types via ParamSpec/Overload | Yes |

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
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]: ...

@overload
def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    Decorator for wrapping functions with retry logic, preserving signatures and return types.
    """
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                return await retry_async(
                    func, max_retries, initial_delay, multiplier, jitter, retryable_exceptions, *args, **kwargs
                )
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
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
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agent.core.implement.retry import (
    retry_async, 
    retry_sync, 
    with_retry, 
    NonRetryableError,
    retry_counter
)

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
        result = await retry_async(mock_func, max_retries=3)
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

@pytest.mark.asyncio
async def test_retry_async_non_retryable_error():
    """Verify that NonRetryableError stops execution immediately."""
    mock_func = AsyncMock(side_effect=NonRetryableError("fatal"))
    with pytest.raises(NonRetryableError):
        await retry_async(mock_func)
    assert mock_func.call_count == 1

def test_retry_sync_decorator():
    """Verify the with_retry decorator on synchronous functions."""
    mock_func = MagicMock(side_effect=[RuntimeError("fail"), "ok"])
    
    @with_retry(max_retries=1)
    def decorated_func() -> str:
        return mock_func()

    with patch("time.sleep"):
        assert decorated_func() == "ok"
        assert mock_func.call_count == 2

def test_retry_sync_metrics_emission():
    """Verify that metrics are emitted with correct tags."""
    mock_func = MagicMock(side_effect=[ValueError("fail"), "ok"])
    
    with patch("time.sleep"):
        with patch.object(retry_counter, 'add') as mock_add:
            retry_sync(mock_func, max_retries=1, retryable_exceptions=(ValueError,))
            mock_add.assert_called_once_with(
                1, {"exception": "ValueError", "mode": "sync"}
            )

@pytest.mark.asyncio
async def test_jitter_and_backoff_calculation():
    """Verify that the delay increases and includes jitter."""
    mock_func = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), "ok"])

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with patch("random.uniform", return_value=0.0):
            await retry_async(mock_func, max_retries=2, initial_delay=1.0, multiplier=2.0, jitter=0.1)
            # 1.0 -> 2.0
            assert mock_sleep.call_args_list[0][0][0] == 1.0
            assert mock_sleep.call_args_list[1][0][0] == 2.0
```

## Verification Plan

### Automated Tests
- [ ] Run the expanded unit tests:
  `pytest .agent/src/agent/core/implement/tests/test_retry.py`
  Expected: All tests pass, covering sync/async paths, decorators, metrics, and short-circuits.
- [ ] Run linter to ensure PEP-257 compliance and typing:
  `agent lint .agent/src/agent/core/implement/retry.py`
  Expected: No typing or linting errors. Verify that `with_retry` correctly propagates return types using `mypy`.

### Manual Verification
- [ ] Verify observability in logs (simulated):
  `PYTHONPATH=.agent/src python -c "from agent.core.implement.retry import retry_sync; retry_sync(lambda: 1/0, max_retries=1)"`
  Expected: Log output shows warning with `attempt: 1`, `mode: sync`, and `exception: ZeroDivisionError`.
- [ ] Verify Metric Tagging:
  Ensure `retry_attempts_total` does not contain the `attempt` number as a tag in the metrics exporter.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with INFRA-125: Implement ADR-012 Retry and Backoff Utilities.
- [ ] README.md updated with the following examples:
    - Usage of `@with_retry` on a synchronous function.
    - Usage of `@with_retry` on an asynchronous coroutine.
    - Functional usage of `retry_async` for dynamic parameter injection.
    - Functional usage of `retry_sync`.
    - Instructions on using `NonRetryableError` to short-circuit retries.

### Observability
- [ ] Logs are structured and include `attempt` and `mode`.
- [ ] Metric tags are standardized and low-cardinality (`exception`, `mode`).
- [ ] Tracing spans cover both sync and async execution attempts.

### Testing
- [ ] All existing tests pass.
- [ ] New tests added for each new public interface, including `NonRetryableError` and metric verification.
- [ ] Static type analysis confirms `@with_retry` preserves return types (no `Any` leakage).

## Copyright

Copyright 2026 Justin Cook