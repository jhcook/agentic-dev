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

from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from agent.commands.workflow import pr

runner = CliRunner()

# Wrap the pr function in a Typer app for CliRunner invocation
test_app = typer.Typer()
test_app.command()(pr)


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.workflow.preflight")
@patch("agent.commands.workflow.infer_story_id", return_value="TEST-100")
@patch("subprocess.check_output")
@patch("subprocess.run")
def test_pr_title_format(mock_run, mock_check_out, mock_infer, mock_preflight, mock_sm):
    """Test that PR title includes [STORY-ID] prefix."""
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_check_out.return_value = b"fix: resolve auth bug"
    mock_run.return_value = MagicMock(returncode=0)

    result = runner.invoke(test_app, ["--skip-preflight"])

    assert result.exit_code == 0
    # Verify the title passed to gh includes the story ID
    call_args = mock_run.call_args[0][0]
    assert "[TEST-100]" in call_args[call_args.index("--title") + 1]


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.workflow.infer_story_id", return_value="TEST-100")
@patch("subprocess.check_output")
@patch("subprocess.run")
def test_pr_skip_preflight_logs_warning(mock_run, mock_check_out, mock_infer, mock_sm):
    """Test that --skip-preflight logs a timestamped audit warning."""
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_check_out.return_value = b"chore: update deps"
    mock_run.return_value = MagicMock(returncode=0)

    result = runner.invoke(test_app, ["--skip-preflight"])

    assert result.exit_code == 0
    assert "Preflight SKIPPED" in result.stdout
    # Verify timestamp is in the output (format: YYYY-MM-DDTHH:MM:SS)
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result.stdout)
    # Verify governance status in body reflects skipped
    call_args = mock_run.call_args[0][0]
    body = call_args[call_args.index("--body") + 1]
    assert "Preflight Skipped" in body


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.workflow.infer_story_id", return_value="TEST-100")
@patch("subprocess.check_output")
@patch("subprocess.run")
def test_pr_gh_not_found(mock_run, mock_check_out, mock_infer, mock_sm):
    """Test that missing gh CLI fails gracefully with clear error."""
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_check_out.return_value = b"feat: new feature"
    mock_run.side_effect = FileNotFoundError("gh not found")

    result = runner.invoke(test_app, ["--skip-preflight"])

    assert result.exit_code == 1
    assert "'gh' CLI not found" in result.stdout


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.core.utils.scrub_sensitive_data", wraps=lambda x: x.replace("SECRET", "[REDACTED]"))
@patch("agent.commands.workflow.infer_story_id", return_value="TEST-100")
@patch("subprocess.check_output")
@patch("subprocess.run")
def test_pr_body_scrubbing(mock_run, mock_check_out, mock_infer, mock_scrub, mock_sm):
    """Test that PR body is passed through scrub_sensitive_data."""
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_check_out.return_value = b"fix: update"
    mock_run.return_value = MagicMock(returncode=0)

    result = runner.invoke(test_app, ["--skip-preflight"])

    assert result.exit_code == 0
    # Verify scrub_sensitive_data was called on the body
    mock_scrub.assert_called_once()
