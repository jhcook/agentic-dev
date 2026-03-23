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

"""Unit tests for exponential backoff and jitter calculations (INFRA-169)."""

import asyncio
import time
import pytest
from agent.core.implement.retry import retry_with_backoff

@pytest.mark.asyncio
async def test_backoff_timing_exponential():
    """Verify that delays increase exponentially between attempts."""
    timings = []
    
    @retry_with_backoff(max_retries=2, base_delay=0.1, backoff_factor=2.0, jitter=False)
    async def flappy_task():
        timings.append(time.time())
        if len(timings) < 3:
            raise RuntimeError("Retry required")
        return True

    start = time.time()
    await flappy_task()
    
    # Intervals should be ~0.1s then ~0.2s
    interval_1 = timings[1] - timings[0]
    interval_2 = timings[2] - timings[1]
    
    assert 0.09 <= interval_1 <= 0.15
    assert 0.19 <= interval_2 <= 0.25

@pytest.mark.asyncio
async def test_jitter_application():
    """Verify that jitter introduces variance in retry timing."""
    timings_1 = []
    timings_2 = []
    
    async def task_logic(log):
        log.append(time.time())
        if len(log) < 2:
            raise RuntimeError("Retry")
        return True

    # Run two identical tasks with jitter and check if they differ
    t1 = retry_with_backoff(max_retries=1, base_delay=0.1, jitter=True)(task_logic)
    t2 = retry_with_backoff(max_retries=1, base_delay=0.1, jitter=True)(task_logic)
    
    await t1(timings_1)
    await t2(timings_2)
    
    delay_1 = timings_1[1] - timings_1[0]
    delay_2 = timings_2[1] - timings_2[0]
    
    # It is extremely unlikely two jittered runs are identical to high precision
    assert delay_1 != delay_2