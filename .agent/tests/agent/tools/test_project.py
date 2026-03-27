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

"""Unit tests for the project domain tools module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.tools.project import read_story, read_runbook, list_stories, match_story


def test_read_story_success(tmp_path):
    """Test successful story retrieval with tmp_path filesystem."""
    stories_dir = tmp_path / ".agent" / "cache" / "stories"
    stories_dir.mkdir(parents=True)
    story_file = stories_dir / "INFRA-143.md"
    story_file.write_text("# INFRA-143\nStatus: COMMITTED")

    with patch("agent.tools.project.validate_safe_path", side_effect=lambda p, r: p):
        result = read_story("INFRA-143", tmp_path)
        assert "INFRA-143" in result
        assert "COMMITTED" in result


def test_read_story_not_found(tmp_path):
    """Validate negative case for non-existent story ID (AC-5)."""
    stories_dir = tmp_path / ".agent" / "cache" / "stories"
    stories_dir.mkdir(parents=True)

    with patch("agent.tools.project.validate_safe_path", side_effect=lambda p, r: p):
        result = read_story("INFRA-999", tmp_path)
        assert "not found" in result.lower()


def test_read_runbook_success(tmp_path):
    """Test successful runbook retrieval."""
    runbooks_dir = tmp_path / ".agent" / "cache" / "runbooks"
    runbooks_dir.mkdir(parents=True)
    runbook_file = runbooks_dir / "INFRA-143-runbook.md"
    runbook_file.write_text("# Runbook for INFRA-143")

    with patch("agent.tools.project.validate_safe_path", side_effect=lambda p, r: p):
        result = read_runbook("INFRA-143", tmp_path)
        assert "Runbook for INFRA-143" in result


def test_list_stories_globbing(tmp_path):
    """Verify story listing handles directory traversal and filtering correctly."""
    stories_dir = tmp_path / ".agent" / "cache" / "stories"
    stories_dir.mkdir(parents=True)
    (stories_dir / "INFRA-143.md").write_text("content")
    (stories_dir / "INFRA-144.md").write_text("content")

    result = list_stories(tmp_path)
    assert "INFRA-143" in result
    assert "INFRA-144" in result


def test_list_stories_empty(tmp_path):
    """Verify graceful handling when stories directory is empty."""
    stories_dir = tmp_path / ".agent" / "cache" / "stories"
    stories_dir.mkdir(parents=True)

    result = list_stories(tmp_path)
    assert "no stories" in result.lower()


def test_match_story_logic(tmp_path):
    """Verify fuzzy matching for story content."""
    stories_dir = tmp_path / ".agent" / "cache" / "stories"
    stories_dir.mkdir(parents=True)
    story = stories_dir / "INFRA-143-migration-project.md"
    story.write_text("# INFRA-143\nTitle: Migration Project and Knowledge Modules")

    result = match_story("migration", tmp_path)
    assert "INFRA-143" in result
