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

"""Unit tests for the knowledge domain tools module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from agent.tools.knowledge import read_adr, read_journey, search_knowledge


def test_read_adr_success(tmp_path):
    """Test ADR retrieval with a real temporary filesystem."""
    adr_dir = tmp_path / ".agent" / "adrs"
    adr_dir.mkdir(parents=True)
    adr_file = adr_dir / "ADR-043-tool-registry-foundation.md"
    adr_file.write_text("# ADR-043: Tool Registry Foundation")

    result = read_adr("ADR-043", tmp_path)
    assert "ADR-043" in result


def test_read_adr_not_found(tmp_path):
    """Test negative case for non-existent ADR ID."""
    adr_dir = tmp_path / ".agent" / "adrs"
    adr_dir.mkdir(parents=True)

    result = read_adr("ADR-999", tmp_path)
    assert "not found" in result.lower()


def test_read_adr_no_directory(tmp_path):
    """Test graceful handling when ADR directory does not exist."""
    result = read_adr("ADR-001", tmp_path)
    assert "not found" in result.lower()


def test_read_journey_success(tmp_path):
    """Test journey retrieval from the knowledge module."""
    journey_dir = tmp_path / ".agent" / "journeys"
    journey_dir.mkdir(parents=True)
    jrn_file = journey_dir / "JRN-072.md"
    jrn_file.write_text("# JRN-072: Terminal Console TUI Chat")

    with patch("agent.tools.knowledge.validate_safe_path", side_effect=lambda p, r: p):
        result = read_journey("JRN-072", tmp_path)
        assert "JRN-072" in result


@pytest.mark.asyncio
async def test_search_knowledge_ranked_results():
    """Test that search_knowledge returns ranked results from RAG service (AC-3)."""
    mock_result_1 = MagicMock()
    mock_result_1.id = "ADR-043"
    mock_result_1.score = 0.12
    mock_result_1.content = "Content for ADR-043 about tool registry"

    mock_result_2 = MagicMock()
    mock_result_2.id = "INFRA-143"
    mock_result_2.score = 0.45
    mock_result_2.content = "Content for INFRA-143 migration"

    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(return_value=[mock_result_1, mock_result_2])
    mock_rag_module = MagicMock()
    mock_rag_module.rag_service = mock_rag

    with patch.dict("sys.modules", {"agent.core.ai.rag": mock_rag_module}):
        result = await search_knowledge("registry design")
        assert "ADR-043" in result
        assert "INFRA-143" in result


@pytest.mark.asyncio
async def test_search_knowledge_no_results():
    """Test that search_knowledge handles empty results gracefully."""
    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(return_value=[])
    mock_rag_module = MagicMock()
    mock_rag_module.rag_service = mock_rag

    with patch.dict("sys.modules", {"agent.core.ai.rag": mock_rag_module}):
        result = await search_knowledge("nonexistent topic")
        assert "no matching" in result.lower()

