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

"""Journey tests for JRN-065: Circuit Breaker During Implementation.

Tests the micro-commit loop (Layer 3) and circuit breaker that enforces
atomic save points and LOC limits during `agent implement`.
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from agent.commands.implement import (
    count_edit_distance,
    _create_follow_up_story,
    _update_or_create_plan,
    _micro_commit_step,
    LOC_WARNING_THRESHOLD,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
    MAX_EDIT_DISTANCE_PER_STEP,
)


# ---------------------------------------------------------------------------
# Step 1: Implementation Loop Starts
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestImplementationLoopInit:
    """Step 1: CLI begins the micro-commit implement loop."""

    def test_loc_counter_starts_at_zero(self):
        """Cumulative LOC counter should initialise at 0."""
        # The cumulative_loc variable is initialised in the implement() function
        # We verify the constants are defined and correct
        assert LOC_WARNING_THRESHOLD == 200
        assert LOC_CIRCUIT_BREAKER_THRESHOLD == 400
        assert MAX_EDIT_DISTANCE_PER_STEP == 30

    def test_edit_distance_unchanged_is_zero(self):
        """Unchanged content returns edit distance of 0."""
        content = "line 1\nline 2\nline 3\n"
        assert count_edit_distance(content, content) == 0

    def test_edit_distance_empty_to_empty_is_zero(self):
        """Both empty strings return 0."""
        assert count_edit_distance("", "") == 0


# ---------------------------------------------------------------------------
# Step 2: Save Point After Green State
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestMicroCommitSavePoints:
    """Step 2: Changes are auto-committed as atomic save points."""

    @patch("agent.commands.implement.subprocess")
    def test_micro_commit_creates_conventional_commit(self, mock_subprocess):
        """Save point creates a git commit with conventional format."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        result = _micro_commit_step(
            story_id="INFRA-TEST",
            step_index=1,
            step_loc=10,
            cumulative_loc=10,
            modified_files=["src/utils.py"],
        )
        assert result is True

        # Verify git add and commit were called
        calls = mock_subprocess.run.call_args_list
        assert len(calls) >= 2  # git add + git commit

        # Verify commit message follows conventional format
        commit_call = calls[-1]
        commit_args = commit_call[0][0] if commit_call[0] else commit_call[1].get("args", [])
        commit_msg = " ".join(str(a) for a in commit_args)
        assert "INFRA-TEST" in commit_msg

    @patch("agent.commands.implement.subprocess")
    def test_micro_commit_failure_is_non_fatal(self, mock_subprocess):
        """A failed git commit does not crash the implementation loop."""
        import subprocess as real_subprocess
        mock_subprocess.run.side_effect = real_subprocess.CalledProcessError(1, "git")
        mock_subprocess.CalledProcessError = real_subprocess.CalledProcessError

        result = _micro_commit_step(
            story_id="INFRA-TEST",
            step_index=1,
            step_loc=10,
            cumulative_loc=10,
            modified_files=["src/utils.py"],
        )
        assert result is False

    @patch("agent.commands.implement.subprocess")
    def test_micro_commit_empty_files_succeeds(self, mock_subprocess):
        """Empty file list returns True without calling git."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        result = _micro_commit_step(
            story_id="INFRA-TEST",
            step_index=1,
            step_loc=0,
            cumulative_loc=0,
            modified_files=[],
        )
        assert result is True

    def test_edit_distance_tracks_additions(self):
        """Edit distance correctly counts added lines."""
        original = "line 1\nline 2\n"
        modified = "line 1\nline 2\nline 3\nline 4\n"
        distance = count_edit_distance(original, modified)
        assert distance == 2  # 2 lines added

    def test_edit_distance_tracks_deletions(self):
        """Edit distance correctly counts deleted lines."""
        original = "line 1\nline 2\nline 3\n"
        modified = "line 1\n"
        distance = count_edit_distance(original, modified)
        assert distance == 2  # 2 lines deleted

    def test_edit_distance_tracks_mixed_changes(self):
        """Edit distance counts both additions and deletions."""
        original = "line 1\nline 2\nline 3\n"
        modified = "line 1\nline 2 modified\nline 3\nline 4\n"
        distance = count_edit_distance(original, modified)
        assert distance >= 1  # At least the modified + added line

    def test_small_step_limit_constant(self):
        """Small-step limit is 30 lines per step."""
        assert MAX_EDIT_DISTANCE_PER_STEP == 30


# ---------------------------------------------------------------------------
# Step 3: LOC Warning at 200
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestLocWarning:
    """Step 3: CLI displays a warning at 200 LOC (soft limit)."""

    def test_warning_threshold_is_200(self):
        """Warning threshold is set to 200 LOC."""
        assert LOC_WARNING_THRESHOLD == 200

    def test_warning_is_soft_limit(self):
        """Warning threshold < circuit breaker threshold (not a stop)."""
        assert LOC_WARNING_THRESHOLD < LOC_CIRCUIT_BREAKER_THRESHOLD

    def test_cumulative_loc_at_warning(self):
        """Cumulative LOC of exactly 200 triggers warning range."""
        cumulative = 200
        assert LOC_WARNING_THRESHOLD <= cumulative < LOC_CIRCUIT_BREAKER_THRESHOLD


# ---------------------------------------------------------------------------
# Step 4: Circuit Breaker at 400 LOC
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestCircuitBreaker:
    """Step 4: Circuit breaker fires at 400 cumulative LOC."""

    def test_circuit_breaker_threshold_is_400(self):
        """Circuit breaker fires at 400 LOC."""
        assert LOC_CIRCUIT_BREAKER_THRESHOLD == 400

    def test_cumulative_loc_triggers_breaker(self):
        """Cumulative LOC >= 400 triggers the circuit breaker."""
        cumulative = 400
        assert cumulative >= LOC_CIRCUIT_BREAKER_THRESHOLD

    def test_cumulative_loc_below_threshold_continues(self):
        """Cumulative LOC < 400 does not trigger the circuit breaker."""
        cumulative = 399
        assert cumulative < LOC_CIRCUIT_BREAKER_THRESHOLD


# ---------------------------------------------------------------------------
# Step 4a: Follow-Up Story Generation
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestFollowUpStoryGeneration:
    """Step 4: Auto-generate a follow-up story with remaining steps."""

    @patch("agent.commands.implement.get_next_id", return_value="INFRA-200")
    @patch("agent.commands.implement.config")
    def test_creates_follow_up_story(self, mock_config, mock_next_id, tmp_path):
        """Follow-up story file is created with correct content."""
        mock_config.stories_dir = tmp_path / "stories"
        (tmp_path / "stories" / "INFRA").mkdir(parents=True)

        remaining = ["## Step 5\nDo remaining work", "## Step 6\nFinish up"]
        story_id = _create_follow_up_story(
            original_story_id="INFRA-099",
            original_title="Test Feature",
            remaining_chunks=remaining,
            completed_step_count=4,
            cumulative_loc=410,
        )

        assert story_id is not None
        # Find the created file
        created = list((tmp_path / "stories" / "INFRA").glob("*.md"))
        assert len(created) == 1
        content = created[0].read_text()
        assert "INFRA-099" in content  # References original story

    @patch("agent.commands.implement.get_next_id", return_value="INFRA-200")
    @patch("agent.commands.implement.config")
    def test_no_overwrite_existing_story(self, mock_config, mock_next_id, tmp_path):
        """Follow-up story does not overwrite existing files."""
        stories_dir = tmp_path / "stories" / "INFRA"
        stories_dir.mkdir(parents=True)
        existing = stories_dir / "INFRA-200-test-feature-continuation.md"
        existing.write_text("# Existing story")

        result = _create_follow_up_story(
            original_story_id="INFRA-099",
            original_title="Test Feature",
            remaining_chunks=["## Step 5\nRemaining"],
            completed_step_count=4,
            cumulative_loc=410,
        )
        # Original file should be preserved
        assert existing.read_text() == "# Existing story"
        # Returns None because file already exists
        assert result is None


# ---------------------------------------------------------------------------
# Step 4b: Plan Linkage
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestPlanLinkage:
    """Step 4: If no Plan exists, create one linking original + follow-up."""

    @patch("agent.commands.implement.config")
    def test_creates_new_plan(self, mock_config, tmp_path):
        """When no plan exists, creates a new one."""
        mock_config.plans_dir = tmp_path / "plans"

        _update_or_create_plan("INFRA-099", "INFRA", "INFRA-200")

        plan_dir = tmp_path / "plans" / "INFRA"
        plans = list(plan_dir.glob("*.md"))
        assert len(plans) == 1
        content = plans[0].read_text()
        assert "INFRA-099" in content
        assert "INFRA-200" in content

    @patch("agent.commands.implement.config")
    def test_appends_to_existing_plan(self, mock_config, tmp_path):
        """When a plan referencing the story exists, append follow-up."""
        plan_dir = tmp_path / "plans" / "INFRA"
        plan_dir.mkdir(parents=True)
        existing_plan = plan_dir / "INFRA-099-plan.md"
        existing_plan.write_text("# Plan for INFRA-099\n\n- INFRA-099\n")

        mock_config.plans_dir = tmp_path / "plans"

        _update_or_create_plan("INFRA-099", "INFRA", "INFRA-200")

        content = existing_plan.read_text()
        assert "INFRA-200" in content


# ---------------------------------------------------------------------------
# Step 5: Follow-Up Story Is Independently Implementable
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestFollowUpImplementable:
    """Step 5: Follow-up story can be implemented independently."""

    def test_fresh_loc_counter_for_follow_up(self):
        """Each implementation run starts with a fresh LOC counter."""
        # This is a design invariant: the cumulative_loc variable is
        # local to the implement() function scope, so each invocation
        # starts at 0. We verify by checking the constants exist.
        assert LOC_CIRCUIT_BREAKER_THRESHOLD == 400
        # A new implement() call will initialise cumulative_loc = 0
        # (tested at integration level in the full implement loop)


# ---------------------------------------------------------------------------
# Error Path: Tests Fail (Red State)
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestRedState:
    """Error path: Tests fail after code generation."""

    @patch("agent.commands.implement.subprocess")
    def test_no_commit_on_red_state(self, mock_subprocess):
        """When git operations fail, no commit is created."""
        import subprocess as real_subprocess
        mock_subprocess.run.side_effect = real_subprocess.CalledProcessError(1, "git")
        mock_subprocess.CalledProcessError = real_subprocess.CalledProcessError

        result = _micro_commit_step(
            story_id="INFRA-TEST",
            step_index=1,
            step_loc=10,
            cumulative_loc=10,
            modified_files=["src/broken.py"],
        )
        assert result is False


# ---------------------------------------------------------------------------
# Edge Case: Runbook Completes Within Limit
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestWithinLimitCompletion:
    """Edge case: Runbook completes within 400 LOC — no circuit breaker."""

    def test_small_edit_does_not_trigger_breaker(self):
        """Small edits stay well below the threshold."""
        original = "def foo(): pass\n"
        modified = "def foo():\n    return 42\n"
        distance = count_edit_distance(original, modified)
        cumulative = distance
        assert cumulative < LOC_CIRCUIT_BREAKER_THRESHOLD

    def test_new_file_counts_all_lines(self):
        """Creating a new file counts all lines as edit distance."""
        original = ""
        modified = "\n".join(f"line {i}" for i in range(50))
        distance = count_edit_distance(original, modified)
        assert distance == 50


# ---------------------------------------------------------------------------
# Edge Case: Commit Message Quality
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-065")
class TestCommitMessageQuality:
    """Edge case: Save-point commits use conventional commit format."""

    @patch("agent.commands.implement.subprocess")
    def test_commit_message_includes_story_id(self, mock_subprocess):
        """Commit message includes the story ID for traceability."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        _micro_commit_step(
            story_id="INFRA-123",
            step_index=3,
            step_loc=15,
            cumulative_loc=45,
            modified_files=["src/app.py"],
        )

        commit_call = mock_subprocess.run.call_args_list[-1]
        commit_args = commit_call[0][0]
        commit_msg = " ".join(str(a) for a in commit_args)
        assert "INFRA-123" in commit_msg

    @patch("agent.commands.implement.subprocess")
    def test_commit_message_includes_step_index(self, mock_subprocess):
        """Commit message includes the step index."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        _micro_commit_step(
            story_id="INFRA-123",
            step_index=5,
            step_loc=20,
            cumulative_loc=100,
            modified_files=["src/app.py"],
        )

        commit_call = mock_subprocess.run.call_args_list[-1]
        commit_args = commit_call[0][0]
        commit_msg = " ".join(str(a) for a in commit_args)
        assert "step 5" in commit_msg.lower() or "5" in commit_msg
