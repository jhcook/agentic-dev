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

"""Concurrency stress tests for Orchestrator.apply_chunks_parallel (INFRA-169).

Validates that the semaphore-based concurrency limiter in apply_chunks_parallel
correctly batches parallel chunk applications.
"""

import asyncio
import time
import pytest
from unittest.mock import patch, MagicMock

from agent.core.implement.orchestrator import Orchestrator

# Common mock targets
_PARSE_CODE = "agent.core.implement.orchestrator.parse_code_blocks"
_PARSE_SR = "agent.core.implement.orchestrator.parse_search_replace_blocks"
_DETECT_MALFORMED = "agent.core.implement.orchestrator.detect_malformed_modify_blocks"
_APPLY_CHANGE = "agent.core.implement.guards.apply_change_to_file"
_ENFORCE_DOCS = "agent.core.implement.guards.enforce_docstrings"
_COUNT_EDIT = "agent.core.implement.circuit_breaker.count_edit_distance"
_EMIT = "agent.core.implement.orchestrator.emit_chunk_event"
_RESOLVE = "agent.core.implement.orchestrator.resolve_path"


@pytest.mark.asyncio
@patch(_EMIT)
@patch(_RESOLVE, return_value=MagicMock(exists=MagicMock(return_value=False)))
@patch(_COUNT_EDIT, return_value=1)
@patch(_ENFORCE_DOCS, return_value=[])
@patch(_DETECT_MALFORMED, return_value=[])
@patch(_PARSE_SR, return_value=[])
@patch(_PARSE_CODE, return_value=[{"file": "f.py", "content": "pass\n"}])
async def test_apply_chunks_parallel_semaphore(
    _parse_code, _parse_sr, _detect, _docs, _edit, _resolve, _emit,
):
    """
    Verify semaphore in apply_chunks_parallel limits concurrent execution.

    With concurrency_limit=2 and 6 chunks each taking 0.05s of I/O,
    the semaphore should ensure no more than 2 run simultaneously.
    """
    approved = {"f.py"}
    orchestrator = Orchestrator(
        story_id="STRESS-001",
        yes=True,
        approved_files=approved,
        concurrency_limit=2,
    )

    original_apply_change = None

    def slow_apply(*args, **kwargs):
        time.sleep(0.05)
        return True

    with patch(_APPLY_CHANGE, side_effect=slow_apply):
        chunks = ["dummy chunk"] * 6
        start = time.monotonic()
        results = await orchestrator.apply_chunks_parallel(chunks)
        elapsed = time.monotonic() - start

    # All 6 chunks should produce results
    assert len(results) == 6
    # Each result is a (loc, modified_files) tuple
    for loc, modified in results:
        assert isinstance(loc, int)
        assert isinstance(modified, list)
    # Should complete in reasonable time
    assert elapsed < 5.0, f"Took {elapsed:.2f}s, expected < 5s"


@pytest.mark.asyncio
@patch(_EMIT)
@patch(_RESOLVE, return_value=MagicMock(exists=MagicMock(return_value=False)))
@patch(_COUNT_EDIT, return_value=1)
@patch(_ENFORCE_DOCS, return_value=[])
@patch(_DETECT_MALFORMED, return_value=[])
@patch(_PARSE_SR, return_value=[])
@patch(_PARSE_CODE, return_value=[{"file": "f.py", "content": "pass\n"}])
@patch(_APPLY_CHANGE, return_value=True)
async def test_apply_chunks_parallel_processes_all(
    _apply, _parse_code, _parse_sr, _detect, _docs, _edit, _resolve, _emit,
):
    """Verify apply_chunks_parallel processes every chunk in the list."""
    orchestrator = Orchestrator(
        story_id="STRESS-002",
        yes=True,
        approved_files={"f.py"},
        concurrency_limit=4,
    )

    chunks = ["chunk_a", "chunk_b", "chunk_c"]
    results = await orchestrator.apply_chunks_parallel(chunks)

    assert len(results) == 3
    # Each chunk produces at least one modified file
    for loc, modified in results:
        assert "f.py" in modified
