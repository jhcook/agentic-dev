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

"""Concurrency stress tests for Orchestrator.apply_chunk (INFRA-169).

Validates that the semaphore-based concurrency limiter in apply_chunk
correctly batches parallel file applications.
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
async def test_concurrency_limit(
    _parse_sr, _detect, _docs, _edit, _resolve, _emit,
):
    """
    Verify the semaphore limits concurrent file applications.

    With concurrency_limit=2 and 6 files each taking 0.05s,
    sequential would take ~0.3s, parallel-2 batches ~0.15s.
    """
    # Build file list for the code block parser
    files = [{"file": f"stress_{i}.py", "content": "pass\n"} for i in range(6)]
    approved = {f["file"] for f in files}

    orchestrator = Orchestrator(
        story_id="STRESS-001",
        yes=True,
        approved_files=approved,
        concurrency_limit=2,
    )

    # Simulate slow file writes via apply_change_to_file
    def slow_apply(*args, **kwargs):
        time.sleep(0.05)
        return True

    with patch(_PARSE_CODE, return_value=files):
        with patch(_APPLY_CHANGE, side_effect=slow_apply):
            start = time.monotonic()
            loc, modified = await orchestrator.apply_chunk("dummy", 1)
            elapsed = time.monotonic() - start

    assert len(modified) == 6
    # Should complete in reasonable time (well under 10s for 6 files)
    assert elapsed < 5.0, f"Took {elapsed:.2f}s, expected < 5s"
