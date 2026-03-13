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
        """Mock decorated sync function."""
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