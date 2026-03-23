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

"""Stress tests for high-volume concurrent generation (INFRA-169)."""

import asyncio
import time
import pytest
from unittest.mock import patch, AsyncMock
from agent.core.implement.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_orchestrator_concurrency_limit():
    """
    Verify that the concurrency limiter (semaphore) prevents resource exhaustion.
    If semaphore is 5 and we have 10 tasks of 0.1s, it should take ~0.2s.
    """
    orchestrator = Orchestrator(story_id="STRESS-001", yes=True)
    
    async def slow_apply(*args, **kwargs):
        await asyncio.sleep(0.1)
        return True

    with patch("agent.core.implement.guards.apply_change_to_file", side_effect=slow_apply):
        # Construct a massive chunk with 10 files
        content_parts = []
        for i in range(10):
            content_parts.append(f"#### [NEW] stress_{i}.py\n```python\npass\n```")
