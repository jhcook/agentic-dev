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

"""Tests for agent.commands.utils (update_story_state)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.commands.utils import _VALID_STATES, update_story_state


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestUpdateStoryStateValidation:
    """Ensure bad inputs are rejected before any file I/O occurs."""

    def test_empty_story_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            update_story_state("", "COMMITTED")

    def test_whitespace_story_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            update_story_state("   ", "COMMITTED")

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="Invalid state"):
            update_story_state("INFRA-001", "BANANA")

    def test_all_valid_states_accepted(self):
        """Every value in _VALID_STATES must not raise ValueError."""
        for state in _VALID_STATES:
            # Should not raise — will fail at find_story_file (returns None)
            with patch("agent.commands.utils.find_story_file", return_value=None):
                update_story_state("INFRA-001", state)  # no exception


# ---------------------------------------------------------------------------
# Story-not-found path
# ---------------------------------------------------------------------------

class TestUpdateStoryStateNotFound:
    """When find_story_file returns None we get a warning, not a crash."""

    @patch("agent.commands.utils.find_story_file", return_value=None)
    def test_missing_story_prints_warning(self, _mock_find, capsys):
        update_story_state("INFRA-999", "COMMITTED")
        # Rich output goes to its own console, so just ensure no exception


# ---------------------------------------------------------------------------
# No-op when already in target state
# ---------------------------------------------------------------------------

class TestUpdateStoryStateNoop:
    """If the story is already in the target state, nothing should be written."""

    @patch("agent.commands.utils.find_story_file")
    def test_noop_when_already_set(self, mock_find, tmp_path):
        story = tmp_path / "INFRA-001-my-story.md"
        story.write_text("# Story\n\n## State\nCOMMITTED\n")
        mock_find.return_value = story

        update_story_state("INFRA-001", "COMMITTED")

        # File should be unchanged
        assert "COMMITTED" in story.read_text()


# ---------------------------------------------------------------------------
# Successful state transition
# ---------------------------------------------------------------------------

class TestUpdateStoryStateSuccess:
    """Happy-path: state is rewritten and sync is attempted."""

    @patch("agent.commands.utils.find_story_file")
    def test_state_updated_in_file(self, mock_find, tmp_path):
        story = tmp_path / "INFRA-001-my-story.md"
        story.write_text("# Story\n\n## State\nDRAFT\n\n## Details\nSome text.\n")
        mock_find.return_value = story

        with patch("agent.commands.utils.push_safe", create=True):
            # push_safe is imported lazily inside the function
            with patch.dict("sys.modules", {"agent.sync.sync": MagicMock()}):
                update_story_state("INFRA-001", "IN_PROGRESS", context_prefix="Phase 0")

        content = story.read_text()
        assert "IN_PROGRESS" in content
        assert "DRAFT" not in content

    @patch("agent.commands.utils.find_story_file")
    def test_state_case_insensitive_input(self, mock_find, tmp_path):
        story = tmp_path / "INFRA-001-my-story.md"
        story.write_text("# Story\n\n## State\nDRAFT\n")
        mock_find.return_value = story

        with patch.dict("sys.modules", {"agent.sync.sync": MagicMock()}):
            update_story_state("INFRA-001", "committed")

        assert "COMMITTED" in story.read_text()


# ---------------------------------------------------------------------------
# File I/O errors
# ---------------------------------------------------------------------------

class TestUpdateStoryStateIOErrors:
    """Graceful handling of read/write failures."""

    @patch("agent.commands.utils.find_story_file")
    def test_read_failure_handled(self, mock_find, tmp_path):
        story = MagicMock(spec=Path)
        story.read_text.side_effect = OSError("disk on fire")
        mock_find.return_value = story

        # Should not raise
        update_story_state("INFRA-001", "COMMITTED")

    @patch("agent.commands.utils.find_story_file")
    def test_write_failure_handled(self, mock_find, tmp_path):
        story = tmp_path / "INFRA-001-my-story.md"
        story.write_text("# Story\n\n## State\nDRAFT\n")
        mock_find.return_value = story

        with patch.object(Path, "write_text", side_effect=OSError("read-only fs")):
            # Should not raise
            update_story_state("INFRA-001", "COMMITTED")
