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

"""Tests for micro-commit circuit breaker (INFRA-095)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.commands.implement import (
    count_edit_distance,
    _create_follow_up_story,
    _update_or_create_plan,
    _micro_commit_step,
)


# ---------------------------------------------------------------------------
# count_edit_distance tests
# ---------------------------------------------------------------------------

class TestCountEditDistance:
    """Tests for the count_edit_distance helper."""

    def test_unchanged_returns_zero(self):
        content = "line1\nline2\nline3\n"
        assert count_edit_distance(content, content) == 0

    def test_both_empty_returns_zero(self):
        assert count_edit_distance("", "") == 0

    def test_additions_only(self):
        original = "line1\nline2\n"
        modified = "line1\nline2\nline3\nline4\n"
        # 2 lines added
        assert count_edit_distance(original, modified) == 2

    def test_deletions_only(self):
        original = "line1\nline2\nline3\n"
        modified = "line1\n"
        # 2 lines deleted
        assert count_edit_distance(original, modified) == 2

    def test_mixed_changes(self):
        original = "line1\nline2\nline3\n"
        modified = "line1\nmodified2\nline3\nline4\n"
        # 1 deletion (line2) + 2 additions (modified2, line4) = 3
        assert count_edit_distance(original, modified) == 3

    def test_new_file_empty_original(self):
        modified = "line1\nline2\nline3\n"
        # All 3 lines are additions
        assert count_edit_distance("", modified) == 3

    def test_deleted_file_empty_modified(self):
        original = "line1\nline2\n"
        # All 2 lines are deletions
        assert count_edit_distance(original, "") == 2

    def test_trailing_newline_variation(self):
        """Ensure trailing newline differences are counted."""
        original = "line1\nline2"
        modified = "line1\nline2\n"
        result = count_edit_distance(original, modified)
        # Should detect the difference (at least 1)
        assert result >= 1


# ---------------------------------------------------------------------------
# _create_follow_up_story tests
# ---------------------------------------------------------------------------

class TestCreateFollowUpStory:
    """Tests for the _create_follow_up_story helper."""

    @patch("agent.commands.implement.get_next_id", return_value="INFRA-999")
    @patch("agent.commands.implement.config")
    def test_creates_story_with_correct_content(self, mock_config, mock_get_next_id, tmp_path):
        mock_config.stories_dir = tmp_path / "stories"

        story_id = _create_follow_up_story(
            "INFRA-001", "Test Title", ["Step 2 content", "Step 3 content"], 1, 450
        )

        assert story_id == "INFRA-999"

        # Find the created file
        story_dir = tmp_path / "stories" / "INFRA"
        assert story_dir.exists()
        files = list(story_dir.glob("INFRA-999-*.md"))
        assert len(files) == 1

        content = files[0].read_text()
        assert "## State\n\nCOMMITTED" in content
        assert "INFRA-001" in content
        assert "Step 2 content" in content
        assert "Step 3 content" in content
        assert "Copyright" in content

    @patch("agent.commands.implement.get_next_id", return_value="INFRA-999")
    @patch("agent.commands.implement.config")
    def test_no_overwrite_existing_file(self, mock_config, mock_get_next_id, tmp_path):
        mock_config.stories_dir = tmp_path / "stories"
        target_dir = tmp_path / "stories" / "INFRA"
        target_dir.mkdir(parents=True)
        target_file = target_dir / "INFRA-999-test-title-continuation.md"
        target_file.write_text("existing content")

        story_id = _create_follow_up_story(
            "INFRA-001", "Test Title", ["Step 2"], 1, 450
        )

        assert story_id is None
        assert target_file.read_text() == "existing content"


# ---------------------------------------------------------------------------
# _micro_commit_step tests
# ---------------------------------------------------------------------------

class TestMicroCommitStep:
    """Tests for the _micro_commit_step helper."""

    @patch("agent.commands.implement.subprocess.run")
    def test_success(self, mock_run):
        success = _micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"])
        assert success is True
        assert mock_run.call_count == 2  # git add + git commit

    @patch("agent.commands.implement.subprocess.run")
    def test_failure_is_non_fatal(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git commit")
        success = _micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"])
        assert success is False

    @patch("agent.commands.implement.subprocess.run")
    def test_empty_files_returns_true(self, mock_run):
        success = _micro_commit_step("INFRA-001", 1, 0, 0, [])
        assert success is True
        mock_run.assert_not_called()

    @patch("agent.commands.implement.subprocess.run")
    def test_commit_message_format(self, mock_run):
        _micro_commit_step("INFRA-042", 3, 25, 100, ["a.py", "b.py"])
        # Check the commit message in the second call (git commit)
        commit_call = mock_run.call_args_list[1]
        commit_args = commit_call[0][0]
        assert "feat(INFRA-042): implement step 3" in commit_args[3]
        assert "25 LOC" in commit_args[3]
        assert "100 cumulative" in commit_args[3]


# ---------------------------------------------------------------------------
# _update_or_create_plan tests
# ---------------------------------------------------------------------------

class TestUpdateOrCreatePlan:
    """Tests for the _update_or_create_plan helper."""

    @patch("agent.commands.implement.config")
    def test_creates_new_plan(self, mock_config, tmp_path):
        mock_config.plans_dir = tmp_path / "plans"
        _update_or_create_plan("INFRA-001", "INFRA-002", "My Feature")

        plan_file = tmp_path / "plans" / "INFRA" / "INFRA-001-plan.md"
        assert plan_file.exists()
        content = plan_file.read_text()
        assert "INFRA-001" in content
        assert "INFRA-002" in content
        assert "Continuation" in content

    @patch("agent.commands.implement.config")
    def test_appends_to_existing_plan(self, mock_config, tmp_path):
        mock_config.plans_dir = tmp_path / "plans"
        plan_dir = tmp_path / "plans" / "INFRA"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "my-plan.md"
        plan_file.write_text("Existing Plan referencing INFRA-001")

        _update_or_create_plan("INFRA-001", "INFRA-002", "My Feature")

        content = plan_file.read_text()
        assert "INFRA-002" in content
        assert "Continuation" in content
        # Original content preserved
        assert "Existing Plan referencing INFRA-001" in content

    @patch("agent.commands.implement.config")
    def test_no_match_creates_new(self, mock_config, tmp_path):
        """When existing plans don't reference the story, create a new one."""
        mock_config.plans_dir = tmp_path / "plans"
        plan_dir = tmp_path / "plans" / "INFRA"
        plan_dir.mkdir(parents=True)
        other_plan = plan_dir / "other-plan.md"
        other_plan.write_text("Plan for INFRA-999 only")

        _update_or_create_plan("INFRA-001", "INFRA-002", "My Feature")

        new_plan = plan_dir / "INFRA-001-plan.md"
        assert new_plan.exists()
        assert "INFRA-002" in new_plan.read_text()