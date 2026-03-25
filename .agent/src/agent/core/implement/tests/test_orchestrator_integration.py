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

"""Integration tests for Orchestrator.apply_chunk (INFRA-169).

These tests mock the guards layer to validate orchestrator routing,
scope checking, and telemetry without touching the filesystem.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.core.implement.orchestrator import Orchestrator

# Common mock targets (all used inside apply_chunk via deferred imports)
_PARSE_CODE = "agent.core.implement.orchestrator.parse_code_blocks"
_PARSE_SR = "agent.core.implement.orchestrator.parse_search_replace_blocks"
_DETECT_MALFORMED = "agent.core.implement.orchestrator.detect_malformed_modify_blocks"
_APPLY_CHANGE = "agent.core.implement.guards.apply_change_to_file"
_APPLY_SR = "agent.core.implement.guards.apply_search_replace_to_file"
_ENFORCE_DOCS = "agent.core.implement.guards.enforce_docstrings"
_COUNT_EDIT = "agent.core.implement.circuit_breaker.count_edit_distance"
_EMIT = "agent.core.implement.orchestrator.emit_chunk_event"
_RESOLVE = "agent.core.implement.orchestrator.resolve_path"


@pytest.fixture
def orchestrator():
    """Create an Orchestrator with scope checking disabled (all files approved)."""
    return Orchestrator(
        story_id="INFRA-169",
        yes=True,
        approved_files={"file1.py", "file2.py", "stress_0.py", "stress_1.py"},
    )


@pytest.mark.asyncio
@patch(_EMIT)
@patch(_RESOLVE, return_value=MagicMock(exists=MagicMock(return_value=False)))
@patch(_COUNT_EDIT, return_value=10)
@patch(_ENFORCE_DOCS, return_value=[])
@patch(_APPLY_CHANGE, return_value=True)
@patch(_DETECT_MALFORMED, return_value=[])
@patch(_PARSE_SR, return_value=[])
@patch(_PARSE_CODE, return_value=[
    {"file": "file1.py", "content": "print(1)\n"},
    {"file": "file2.py", "content": "print(2)\n"},
])
async def test_parallel_chunk_success(
    _parse_code, _parse_sr, _detect, _apply, _docs, _edit, _resolve, _emit,
    orchestrator,
):
    """Verify multiple [NEW] files are processed within a single chunk."""
    loc, modified = await orchestrator.apply_chunk("dummy chunk", 1)

    assert len(modified) == 2
    assert "file1.py" in modified
    assert "file2.py" in modified
    assert loc > 0


@pytest.mark.asyncio
@patch(_EMIT)
@patch(_RESOLVE, return_value=MagicMock(exists=MagicMock(return_value=False)))
@patch(_COUNT_EDIT, return_value=0)
@patch(_ENFORCE_DOCS, return_value=[])
@patch(_APPLY_CHANGE, return_value=True)
@patch(_DETECT_MALFORMED, return_value=[])
@patch(_PARSE_SR, return_value=[])
@patch(_PARSE_CODE, return_value=[])
async def test_empty_chunk_returns_zero(
    _parse_code, _parse_sr, _detect, _apply, _docs, _edit, _resolve, _emit,
    orchestrator,
):
    """An empty chunk (no code blocks found) returns zero LOC and no files."""
    loc, modified = await orchestrator.apply_chunk("", 1)

    assert loc == 0
    assert modified == []


@pytest.mark.asyncio
@patch(_EMIT)
@patch(_RESOLVE, return_value=MagicMock(exists=MagicMock(return_value=False)))
@patch(_COUNT_EDIT, return_value=5)
@patch(_ENFORCE_DOCS, return_value=[])
@patch(_APPLY_CHANGE, return_value=False)
@patch(_DETECT_MALFORMED, return_value=[])
@patch(_PARSE_SR, return_value=[])
@patch(_PARSE_CODE, return_value=[
    {"file": "file1.py", "content": "print(1)\n"},
])
async def test_failed_apply_excludes_from_modified(
    _parse_code, _parse_sr, _detect, _apply, _docs, _edit, _resolve, _emit,
    orchestrator,
):
    """If apply_change_to_file returns False, the file is not in modified list."""
    loc, modified = await orchestrator.apply_chunk("dummy chunk", 1)

    assert modified == []
    assert loc == 0