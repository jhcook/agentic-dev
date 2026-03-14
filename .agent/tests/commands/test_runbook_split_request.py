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

"""Tests for the INFRA-094 SPLIT_REQUEST fallback in runbook generation."""

import json
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.runbook import _parse_split_request, new_runbook

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def app():
    """Create a Typer test app wrapping the new_runbook command."""
    test_app = typer.Typer()
    test_app.command()(new_runbook)
    return test_app


@pytest.fixture
def mock_fs(tmp_path):
    """Mock filesystem for runbook tests with split_requests support."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "runbook-template.md").write_text(
        "# Runbook Template\n## Plan\n<plan>"
    )

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    split_requests_dir = cache_dir / "split_requests"

    with (
        patch("agent.core.config.config.runbooks_dir", tmp_path / "runbooks"),
        patch("agent.core.config.config.agent_dir", tmp_path / ".agent"),
        patch("agent.core.config.config.stories_dir", tmp_path / "stories"),
        patch("agent.core.config.config.templates_dir", templates_dir),
        patch("agent.core.config.config.cache_dir", cache_dir),
        patch(
            "agent.core.config.config.split_requests_dir", split_requests_dir
        ),
        patch(
            "agent.core.context.context_loader.load_context",
            return_value={
                "rules": "Rules",
                "agents": {"description": "", "checks": ""},
                "instructions": "",
                "adrs": "",
            },
        ),
        patch("agent.core.auth.decorators.validate_credentials"),
    ):
        (tmp_path / "runbooks").mkdir()
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "workflows").mkdir()
        (tmp_path / "stories" / "INFRA").mkdir(parents=True)

        yield tmp_path


# ── _parse_split_request Unit Tests ──────────────────────────


VALID_SPLIT_JSON = json.dumps(
    {
        "SPLIT_REQUEST": True,
        "reason": "Story touches 6 files and requires 12 steps",
        "suggestions": [
            "INFRA-094a: Add prompt directive",
            "INFRA-094b: Add response parser and tests",
        ],
    }
)


def test_parse_valid_json():
    """Valid SPLIT_REQUEST JSON is parsed correctly."""
    result = _parse_split_request(VALID_SPLIT_JSON)
    assert result is not None
    assert result["SPLIT_REQUEST"] is True
    assert result["reason"] == "Story touches 6 files and requires 12 steps"
    assert len(result["suggestions"]) == 2


def test_parse_json_in_markdown_fences():
    """SPLIT_REQUEST JSON embedded in markdown code fences is extracted."""
    content = "Here is my analysis:\n```json\n" + VALID_SPLIT_JSON + "\n```\n"
    result = _parse_split_request(content)
    assert result is not None
    assert result["SPLIT_REQUEST"] is True
    assert len(result["suggestions"]) == 2


def test_parse_json_in_fences_no_newline():
    """SPLIT_REQUEST JSON in fences without newlines after opening fence."""
    content = "```json" + VALID_SPLIT_JSON + "```"
    result = _parse_split_request(content)
    assert result is not None
    assert result["SPLIT_REQUEST"] is True


def test_parse_malformed_json_returns_none():
    """Malformed JSON with SPLIT_REQUEST marker returns None (graceful fallback)."""
    content = 'This mentions SPLIT_REQUEST but {"broken json'
    result = _parse_split_request(content)
    assert result is None


def test_parse_normal_runbook_returns_none():
    """Normal runbook content without SPLIT_REQUEST returns None on direct parse."""
    content = "# INFRA-094: Runbook\n\n## Goal\nImplement the feature."
    result = _parse_split_request(content)
    assert result is None


def test_parse_json_without_split_request_key():
    """Valid JSON but without SPLIT_REQUEST key returns None."""
    content = json.dumps({"reason": "test", "suggestions": []})
    result = _parse_split_request(content)
    assert result is None


# ── Integration Tests (CLI) ──────────────────────────────────


def test_split_request_detected_exits_code_2(mock_fs, app):
    """When AI returns SPLIT_REQUEST JSON, CLI saves file and exits with code 2."""
    story_id = "INFRA-TEST"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Simple Story\n- [ ] Step 1")

    with (
        patch("agent.core.ai.ai_service.complete", return_value=VALID_SPLIT_JSON),
        patch("agent.commands.runbook.upsert_artifact"),
    ):
        result = runner.invoke(app, [story_id])

        assert result.exit_code == 2
        assert "AI recommends splitting" in result.stdout

        # Verify JSON saved
        split_file = mock_fs / "cache" / "split_requests" / f"{story_id}.json"
        assert split_file.exists()
        saved_data = json.loads(split_file.read_text())
        assert saved_data["SPLIT_REQUEST"] is True
        assert len(saved_data["suggestions"]) == 2


def test_normal_runbook_proceeds(mock_fs, app):
    """Normal AI response (no SPLIT_REQUEST) writes runbook and exits 0."""
    story_id = "INFRA-NORMAL"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Normal Story\n- [ ] Step 1")

    normal_content = "# INFRA-NORMAL Runbook\n\n## Goal\nDo the thing."

    with (
        patch("agent.core.ai.ai_service.complete", return_value=normal_content),
        patch("agent.commands.runbook.validate_runbook_schema", return_value=[]),
        patch("agent.commands.runbook.upsert_artifact"),
    ):
        result = runner.invoke(app, [story_id])

        assert result.exit_code == 0
        assert "Runbook generated" in result.stdout

        # Runbook file written, not split_requests
        runbook_file = mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md"
        assert runbook_file.exists()
        assert runbook_file.read_text() == normal_content

        # No split request file
        split_file = mock_fs / "cache" / "split_requests" / f"{story_id}.json"
        assert not split_file.exists()


def test_malformed_split_request_falls_back_to_runbook(mock_fs, app):
    """Malformed SPLIT_REQUEST JSON falls back to writing as normal runbook."""
    story_id = "INFRA-MALFORMED"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story\n- [ ] Step 1")

    malformed_content = (
        "# Runbook with SPLIT_REQUEST mentioned but no valid JSON"
    )

    with (
        patch("agent.core.ai.ai_service.complete", return_value=malformed_content),
        patch("agent.commands.runbook.upsert_artifact"),
    ):
        result = runner.invoke(app, [story_id])

        assert result.exit_code == 0
        assert "Runbook generated" in result.stdout

        # Runbook file written with the malformed content as-is
        runbook_file = mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md"
        assert runbook_file.exists()
        assert runbook_file.read_text() == malformed_content


def test_split_request_structured_logging(mock_fs, app):
    """SPLIT_REQUEST event emits structured warning log."""
    story_id = "INFRA-LOG"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story\n- [ ] Step 1")

    with (
        patch("agent.core.ai.ai_service.complete", return_value=VALID_SPLIT_JSON),
        patch("agent.commands.runbook.upsert_artifact"),
        patch("agent.commands.runbook.logger") as mock_logger,
    ):
        result = runner.invoke(app, [story_id])

        assert result.exit_code == 2

        # Verify structured log was emitted
        mock_logger.warning.assert_called()
        log_args = mock_logger.warning.call_args[0]
        assert "split_request" in log_args[0]
        assert log_args[1] == story_id  # story_id
        assert log_args[3] == 2  # suggestion_count
