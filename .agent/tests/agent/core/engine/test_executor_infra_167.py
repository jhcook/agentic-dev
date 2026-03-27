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

"""Tests for TaskExecutor (INFRA-167) — parallel concurrency runner."""

import asyncio
import time

import pytest

from agent.core.engine.executor import TaskExecutor


@pytest.mark.asyncio
async def test_task_executor_parallelism():
    """Validate tasks execute in parallel: total duration < sum of individual durations."""
    executor = TaskExecutor(max_concurrency=5)

    async def slow_task() -> str:
        await asyncio.sleep(0.2)
        return "done"

    tasks = [slow_task for _ in range(3)]

    start = time.monotonic()
    results = await executor.run_parallel(tasks)
    duration = time.monotonic() - start

    assert len(results) == 3
    assert all(r["status"] == "success" for r in results)
    # Sequential would take ~0.6 s; parallel should complete in ~0.2 s
    assert duration < 0.45, f"Execution was too slow for parallel: {duration:.2f}s"


@pytest.mark.asyncio
async def test_task_executor_partial_failure():
    """A single task failure must not prevent other tasks from completing."""
    executor = TaskExecutor(max_concurrency=2)

    async def safe_task() -> str:
        return "Success"

    async def failing_task() -> str:
        raise ValueError("Simulated failure")

    tasks = [safe_task, failing_task, safe_task]
    results = await executor.run_parallel(tasks)

    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "failed"]

    assert len(successes) == 2
    assert len(failures) == 1
    assert "Simulated failure" in failures[0]["error"]


@pytest.mark.asyncio
async def test_task_executor_on_progress_callback():
    """on_progress callback is invoked for each successful task."""
    executor = TaskExecutor(max_concurrency=3)
    completed: list[int] = []

    async def noop_task() -> None:
        return None

    tasks = [noop_task, noop_task, noop_task]
    await executor.run_parallel(tasks, on_progress=lambda idx: completed.append(idx))

    assert len(completed) == 3
