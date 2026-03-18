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

"""Tests for agent.commands.decompose_story (INFRA-157)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.decompose_story import (
    decompose_story,
    get_next_ids,
    _extract_section,
)
from agent.commands.utils import update_story_state

runner = CliRunner()


@pytest.fixture
def app() -> typer.Typer:
    """Minimal Typer app wiring in the decompose_story command."""
    test_app = typer.Typer()
    test_app.command()(decompose_story)
    return test_app


@pytest.fixture
def mock_fs(tmp_path: Path):
    """Temporary filesystem with the directory structure the command expects."""
    stories = tmp_path / "stories" / "INFRA"
    plans = tmp_path / "plans" / "INFRA"
    split_requests = tmp_path / "split_requests"
    templates = tmp_path / "templates"
    for d in (stories, plans, split_requests, templates):
        d.mkdir(parents=True)

    # Minimal story template
    (templates / "story-template.md").write_text(
        "# STORY-XXX: Title\n\n## State\n\nDRAFT\n\n"
        "## Problem Statement\n\nWhat problem are we solving?\n\n"
        "## User Story\n\nAs a <user>, I want <capability> so that <value>.\n\n"
        "## Linked ADRs\n\n- ADR-XXX\n\n{{ COPYRIGHT_HEADER }}\n"
    )
    (templates / "plan-template.md").write_text(
        "# PLAN-XXX: Title\n\n## Summary\n\nSummary.\n\n{{ COPYRIGHT_HEADER }}\n"
    )
    (templates / "license_header.txt").write_text(
        "Copyright 2026 Justin Cook\n"
        "Licensed under the Apache License, Version 2.0\n"
    )

    # Parent story file
    parent = stories / "INFRA-010-parent-story.md"
    parent.write_text(
        "# INFRA-010: Parent Story\n\n## State\n\nCOMMITTED\n\n"
        "## Problem Statement\n\nThe parent problem.\n\n"
        "## Linked ADRs\n\n- ADR-005\n"
    )

    with (
        patch("agent.core.config.config.stories_dir", tmp_path / "stories"),
        patch("agent.core.config.config.plans_dir", tmp_path / "plans"),
        patch("agent.core.config.config.cache_dir", tmp_path),
        patch("agent.core.config.config.templates_dir", templates),
        patch("agent.commands.decompose_story.config.stories_dir", tmp_path / "stories"),
        patch("agent.commands.decompose_story.config.plans_dir", tmp_path / "plans"),
        patch("agent.commands.decompose_story.config.cache_dir", tmp_path),
        patch("agent.commands.decompose_story.config.templates_dir", templates),
        patch("agent.commands.decompose_story.find_story_file", return_value=parent),
        patch("agent.commands.decompose_story.update_story_state"),
    ):
        yield tmp_path


# ---------------------------------------------------------------------------
# AC-1 — Discover split request (missing file → exit 1)
# ---------------------------------------------------------------------------

class TestMissingSplitRequest:
    """Given no split-request JSON → exit code 1 with a clear message."""

    def test_missing_json_exits_1(self, app, mock_fs) -> None:
        """AC-1 negative: no JSON file → exit 1 with expected message."""
        result = runner.invoke(app, ["INFRA-MISSING"])
        assert result.exit_code == 1
        assert "No split request found" in result.output


# ---------------------------------------------------------------------------
# AC-2 / AC-3 / AC-4 / AC-5 — Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    """End-to-end decomposition with a well-formed split-request JSON."""

    def _write_split_request(self, mock_fs: Path, story_id: str) -> None:
        sr_dir = mock_fs / "split_requests"
        sr_dir.mkdir(exist_ok=True)
        (sr_dir / f"{story_id}.json").write_text(
            json.dumps({
                "suggestions": ["Sub-task Alpha", "Sub-task Beta"],
                "reason": "Story is too large.",
            })
        )

    def test_child_story_files_created(self, app, mock_fs) -> None:
        """AC-3: two child story files must be written."""
        self._write_split_request(mock_fs, "INFRA-010")

        with patch(
            "agent.commands.decompose_story.get_next_ids",
            return_value=["INFRA-011", "INFRA-012"],
        ):
            result = runner.invoke(app, ["INFRA-010"])

        assert result.exit_code == 0, result.output
        stories_dir = mock_fs / "stories" / "INFRA"
        assert any(f.name.startswith("INFRA-011") for f in stories_dir.iterdir())
        assert any(f.name.startswith("INFRA-012") for f in stories_dir.iterdir())

    def test_plan_file_created(self, app, mock_fs) -> None:
        """AC-4: a plan file must be written alongside the child stories."""
        self._write_split_request(mock_fs, "INFRA-010")

        with patch(
            "agent.commands.decompose_story.get_next_ids",
            return_value=["INFRA-011", "INFRA-012"],
        ):
            result = runner.invoke(app, ["INFRA-010"])

        assert result.exit_code == 0, result.output
        plans_dir = mock_fs / "plans" / "INFRA"
        assert any(f.name.startswith("INFRA-010") for f in plans_dir.iterdir())

    def test_success_message_printed(self, app, mock_fs) -> None:
        """AC-3/4: success banner must mention the story ID."""
        self._write_split_request(mock_fs, "INFRA-010")

        with patch(
            "agent.commands.decompose_story.get_next_ids",
            return_value=["INFRA-011", "INFRA-012"],
        ):
            result = runner.invoke(app, ["INFRA-010"])

        assert "INFRA-010" in result.output


# ---------------------------------------------------------------------------
# AC-6 — Idempotency guard
# ---------------------------------------------------------------------------

class TestIdempotencyGuard:
    """If a child story file already exists → exit 1, no files written."""

    def test_conflict_exits_1(self, app, mock_fs) -> None:
        """AC-6: pre-existing child file → exit 1, no additional files written."""
        sr_dir = mock_fs / "split_requests"
        (sr_dir / "INFRA-010.json").write_text(
            json.dumps({"suggestions": ["Alpha"], "reason": "Too large."})
        )
        # Pre-create the would-be child file
        stories_dir = mock_fs / "stories" / "INFRA"
        (stories_dir / "INFRA-011-alpha.md").write_text("existing")

        with patch(
            "agent.commands.decompose_story.get_next_ids",
            return_value=["INFRA-011"],
        ):
            result = runner.invoke(app, ["INFRA-010"])

        assert result.exit_code == 1
        assert "Conflict" in result.output or "exist" in result.output.lower()


# ---------------------------------------------------------------------------
# AC-7 — Dry-run mode
# ---------------------------------------------------------------------------

class TestDryRun:
    """--dry-run must preview without writing files."""

    def test_dry_run_no_files_written(self, app, mock_fs) -> None:
        """AC-7: dry-run prints preview and writes nothing."""
        sr_dir = mock_fs / "split_requests"
        (sr_dir / "INFRA-010.json").write_text(
            json.dumps({"suggestions": ["Alpha", "Beta"], "reason": "Too large."})
        )

        before_stories = set((mock_fs / "stories" / "INFRA").iterdir())

        with patch(
            "agent.commands.decompose_story.get_next_ids",
            return_value=["INFRA-011", "INFRA-012"],
        ):
            result = runner.invoke(app, ["INFRA-010", "--dry-run"])

        after_stories = set((mock_fs / "stories" / "INFRA").iterdir())
        assert result.exit_code == 0, result.output
        assert "DRY RUN" in result.output
        assert before_stories == after_stories, "Dry-run must not write any files"


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestGetNextIds:
    """Unit tests for the get_next_ids sequential-ID generator."""

    def test_returns_correct_count(self, tmp_path: Path) -> None:
        """get_next_ids(prefix, n) must return exactly n IDs."""
        with (
            patch("agent.commands.decompose_story.config.stories_dir", tmp_path),
            patch(
                "agent.commands.decompose_story.get_next_id",
                side_effect=["INFRA-020", "INFRA-021", "INFRA-022"],
            ),
        ):
            result = get_next_ids("INFRA", 3)
        assert result == ["INFRA-020", "INFRA-021", "INFRA-022"]

    def test_returns_empty_list_for_zero_count(self, tmp_path: Path) -> None:
        """Requesting 0 IDs must return an empty list without touching the FS."""
        with patch("agent.commands.decompose_story.config.stories_dir", tmp_path):
            result = get_next_ids("INFRA", 0)
        assert result == []

    def test_placeholders_cleaned_up(self, tmp_path: Path) -> None:
        """Temporary placeholder files must not remain after get_next_ids returns."""
        infra_dir = tmp_path / "INFRA"
        infra_dir.mkdir()

        with (
            patch("agent.commands.decompose_story.config.stories_dir", tmp_path),
            patch(
                "agent.commands.decompose_story.get_next_id",
                side_effect=["INFRA-030", "INFRA-031"],
            ),
        ):
            result = get_next_ids("INFRA", 2)

        assert result == ["INFRA-030", "INFRA-031"]
        placeholders = list(infra_dir.glob("*-placeholder.md"))
        assert placeholders == [], f"Placeholders not cleaned up: {placeholders}"

    def test_each_call_to_get_next_id_sees_prior_placeholder(self, tmp_path: Path) -> None:
        """Each successive get_next_id call must be made *after* the previous
        placeholder was written, ensuring monotonically increasing IDs."""
        infra_dir = tmp_path / "INFRA"
        infra_dir.mkdir()
        seen_before_calls: list[set] = []

        def side_effect_capture(directory, prefix):  # noqa: ANN001
            seen_before_calls.append(set(infra_dir.glob("*-placeholder.md")))
            return f"INFRA-{100 + len(seen_before_calls):03d}"

        with (
            patch("agent.commands.decompose_story.config.stories_dir", tmp_path),
            patch(
                "agent.commands.decompose_story.get_next_id",
                side_effect=side_effect_capture,
            ),
        ):
            get_next_ids("INFRA", 3)

        # First call: 0 placeholders. Second call: 1. Third call: 2.
        assert len(seen_before_calls[0]) == 0
        assert len(seen_before_calls[1]) == 1
        assert len(seen_before_calls[2]) == 2

class TestExtractSection:
    """Unit tests for the _extract_section utility."""

    def test_extracts_known_section(self) -> None:
        content = "# Title\n\n## Problem Statement\n\nThe problem.\n\n## State\n\nDRAFT\n"
        assert _extract_section(content, "## Problem Statement") == "The problem."

    def test_missing_section_returns_empty(self) -> None:
        assert _extract_section("# Title\n\n## State\n\nDRAFT\n", "## Nonexistent") == ""


class TestUpdateStoryStateAnnotation:
    """Unit tests for the annotation parameter added to update_story_state for AC-5."""

    def test_annotation_written_to_file(self, tmp_path: Path) -> None:
        story = tmp_path / "story.md"
        story.write_text("# Story\n\n## State\n\nCOMMITTED\n\n## Other\n\nContent\n")

        with patch("agent.commands.utils.find_story_file", return_value=story):
            update_story_state(
                "INFRA-010",
                "SUPERSEDED",
                annotation="(see plan: INFRA-010-plan.md)",
            )

        content = story.read_text()
        assert "SUPERSEDED (see plan: INFRA-010-plan.md)" in content
        assert "COMMITTED" not in content

    def test_idempotent_with_annotation(self, tmp_path: Path) -> None:
        story = tmp_path / "story.md"
        story.write_text(
            "# Story\n\n## State\n\nSUPERSEDED (see plan: INFRA-010-plan.md)\n"
        )
        with patch("agent.commands.utils.find_story_file", return_value=story):
            update_story_state(
                "INFRA-010",
                "SUPERSEDED",
                annotation="(see plan: INFRA-010-plan.md)",
            )
        # File must be unchanged (idempotent)
        content = story.read_text()
        assert content.count("SUPERSEDED") == 1
