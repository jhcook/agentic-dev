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

"""test_retry module."""

import asyncio
import pytest
from agent.core.implement.retry import retry_with_backoff, MaxRetriesExceededError

@pytest.mark.asyncio
async def test_retry_eventual_success():
    """Verify retries succeed if the function eventually returns."""
    calls = 0
    @retry_with_backoff(max_retries=2, base_delay=0.01, jitter=False)
    async def task():
        nonlocal calls
        calls += 1
        if calls < 2: raise ConnectionError("Transient failure")
        return True
    assert await task() is True
    assert calls == 2

@pytest.mark.asyncio
async def test_retry_failure_exhaustion():
    """Verify MaxRetriesExceededError is raised after max attempts."""
    calls = 0
    @retry_with_backoff(max_retries=2, base_delay=0.01, jitter=False)
    async def task():
        nonlocal calls
        calls += 1
        raise ValueError("Permanent failure")
    with pytest.raises(MaxRetriesExceededError):
        await task()
    assert calls == 3  # Initial + 2 retries
