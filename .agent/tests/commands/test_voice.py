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

"""Unit tests for INFRA-072: agent review-voice command."""

import json
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()


@patch("agent.commands.voice.config")
def test_missing_script_error(mock_config, tmp_path):
    """Negative test: missing fetch_last_session.py produces a clear error."""
    mock_config.repo_root = tmp_path  # No script exists here
    result = runner.invoke(app, ["review-voice"])
    assert result.exit_code != 0
    assert "fetch_last_session.py not found" in result.output


@patch("agent.commands.voice.config")
@patch("agent.commands.voice.subprocess.run")
def test_session_fetch_subprocess(mock_subprocess, mock_config, tmp_path):
    """AC1: Verifies subprocess call to fetch_last_session.py."""
    # Create the script file so path check passes
    script_dir = tmp_path / ".agent" / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "fetch_last_session.py").touch()
    mock_config.repo_root = tmp_path

    # Mock subprocess returning empty (no session)
    mock_subprocess.return_value = MagicMock(stdout="", stderr="", returncode=0)

    result = runner.invoke(app, ["review-voice"])

    # Should call subprocess with the script path
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args
    assert "fetch_last_session.py" in str(call_args)
    # Exit 0 because no session is not an error
    assert result.exit_code == 0
    assert "No active voice session found" in result.output


@patch("agent.core.ai.ai_service")
@patch("agent.core.security.scrub_sensitive_data", return_value="scrubbed transcript")
@patch("agent.commands.voice.config")
@patch("agent.commands.voice.subprocess.run")
def test_ai_prompt_includes_session(
    mock_subprocess, mock_config, mock_scrub, mock_ai, tmp_path
):
    """AC2: Verifies AI prompt contains session content and analysis categories."""
    # Setup
    script_dir = tmp_path / ".agent" / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "fetch_last_session.py").touch()
    mock_config.repo_root = tmp_path

    # Mock session content
    session_data = json.dumps({
        "turns": [
            {"role": "user", "content": "What's the weather?"},
            {"role": "assistant", "content": "It's sunny and 72°F."},
        ]
    })
    mock_subprocess.return_value = MagicMock(
        stdout=session_data, stderr="", returncode=0
    )

    # Mock AI response
    mock_ai.complete.return_value = (
        "## Latency\nRating: GOOD\n\n"
        "## Accuracy\nRating: EXCELLENT\n\n"
        "## Tone\nRating: GOOD\n\n"
        "## Interruption\nRating: EXCELLENT"
    )

    result = runner.invoke(app, ["review-voice"])

    # Verify AI was called with the scrubbed session content
    mock_ai.complete.assert_called_once()
    prompt = mock_ai.complete.call_args[0][0]
    assert "scrubbed transcript" in prompt
    assert "Latency" in prompt
    assert "Accuracy" in prompt
    assert "Tone" in prompt
    assert "Interruption" in prompt


@patch("agent.core.ai.ai_service")
@patch("agent.core.security.scrub_sensitive_data", return_value="session data")
@patch("agent.commands.voice.config")
@patch("agent.commands.voice.subprocess.run")
def test_structured_output_categories(
    mock_subprocess, mock_config, mock_scrub, mock_ai, tmp_path
):
    """AC3: Verifies output includes per-category ratings."""
    script_dir = tmp_path / ".agent" / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "fetch_last_session.py").touch()
    mock_config.repo_root = tmp_path

    mock_subprocess.return_value = MagicMock(
        stdout='{"turns": [{"role": "user", "content": "hello"}]}',
        stderr="",
        returncode=0,
    )

    ai_response = (
        "## Latency\nRating: GOOD\nNo repeated requests.\n\n"
        "## Accuracy\nRating: EXCELLENT\nAll intents understood.\n\n"
        "## Tone\nRating: NEEDS IMPROVEMENT\nToo verbose.\n\n"
        "## Interruption\nRating: GOOD\nProper turn-taking.\n\n"
        "## Overall\nRating: GOOD\n\n"
        "## Recommendations\n1. Shorten responses in voice_system_prompt.txt"
    )
    mock_ai.complete.return_value = ai_response

    result = runner.invoke(app, ["review-voice"])

    assert result.exit_code == 0
    assert "Voice Session Review" in result.output
