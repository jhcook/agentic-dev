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

"""Tests for core.implement.circuit_breaker (AC-7, Negative Test)."""

import subprocess
from unittest.mock import patch

import pytest

from agent.core.implement.circuit_breaker import (
    CircuitBreaker,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
    LOC_WARNING_THRESHOLD,
    count_edit_distance,
    create_follow_up_story,
    micro_commit_step,
    update_or_create_plan,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker thresholds and state transitions."""

    def test_initial_state(self):
        """Starts at zero cumulative LOC."""
        cb = CircuitBreaker()
        assert cb.cumulative_loc == 0

    def test_record_accumulates(self):
        """record() sums step LOC into cumulative total."""
        cb = CircuitBreaker()
        cb.record(50)
        cb.record(100)
        assert cb.cumulative_loc == 150

    def test_should_warn_at_threshold(self):
        """should_warn() is True at exactly LOC_WARNING_THRESHOLD."""
        cb = CircuitBreaker()
        cb.record(LOC_WARNING_THRESHOLD)
        assert cb.should_warn() is True

    def test_should_not_warn_below_threshold(self):
        """should_warn() is False below warning threshold."""
        cb = CircuitBreaker()
        cb.record(LOC_WARNING_THRESHOLD - 1)
        assert cb.should_warn() is False

    def test_should_halt_at_breaker_threshold(self):
        """Negative test: should_halt() activates at LOC_CIRCUIT_BREAKER_THRESHOLD (400)."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD)
        assert cb.should_halt() is True

    def test_should_not_halt_below_threshold(self):
        """should_halt() is False below circuit breaker threshold."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD - 1)
        assert cb.should_halt() is False

    def test_warn_is_false_at_halt_threshold(self):
        """should_warn() is False once should_halt() is True."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD)
        assert cb.should_warn() is False


class TestCountEditDistance:
    """Tests for count_edit_distance."""

    def test_unchanged_returns_zero(self):
        """Identical strings produce zero edit distance."""
        c = "line1\nline2\n"
        assert count_edit_distance(c, c) == 0

    def test_added_line(self):
        """Added line is counted."""
        assert count_edit_distance("a\n", "a\nb\n") == 1

    def test_deleted_line(self):
        """Deleted line is counted."""
        assert count_edit_distance("a\nb\n", "a\n") == 1

    def test_both_empty(self):
        """Both empty strings produce zero."""
        assert count_edit_distance("", "") == 0

    def test_new_file(self):
        """New file (empty original) counts all added lines."""
        assert count_edit_distance("", "a\nb\n") == 2


class TestMicroCommitStep:
    """Tests for micro_commit_step."""

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_success(self, mock_run):
        """Returns True and makes two git calls."""
        assert micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"]) is True
        assert mock_run.call_count == 2

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_failure_non_fatal(self, mock_run):
        """Returns False without raising on git failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"]) is False

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_empty_files_skips_git(self, mock_run):
        """Returns True immediately when no files to commit."""
        assert micro_commit_step("INFRA-001", 1, 0, 0, []) is True
        mock_run.assert_not_called()


class TestCreateFollowUpStory:
    """Tests for create_follow_up_story."""

    @patch("agent.core.implement.circuit_breaker.get_next_id", return_value="INFRA-999")
    @patch("agent.core.implement.circuit_breaker.config")
    def test_creates_committed_story(self, mock_config, _mock_id, tmp_path):
        """Created story has COMMITTED state and references the original."""
        mock_config.stories_dir = tmp_path / "stories"
        story_id = create_follow_up_story("INFRA-001", "Test Feature", ["Step 2"], 1, 450)
        assert story_id == "INFRA-999"
        files = list((tmp_path / "stories" / "INFRA").glob("INFRA-999-*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "## State\n\nCOMMITTED" in content
        assert "INFRA-001" in content

    @patch("agent.core.implement.circuit_breaker.get_next_id", return_value="INFRA-999")
    @patch("agent.core.implement.circuit_breaker.config")
    def test_no_overwrite_existing(self, mock_config, _mock_id, tmp_path):
        """Returns None when target story file already exists (collision guard)."""
        mock_config.stories_dir = tmp_path / "stories"
        target = tmp_path / "stories" / "INFRA"
        target.mkdir(parents=True)
        (target / "INFRA-999-test-feature-continuation.md").write_text("existing")
        assert create_follow_up_story("INFRA-001", "Test Feature", ["Step 2"], 1, 450) is None