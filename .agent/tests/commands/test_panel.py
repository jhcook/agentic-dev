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

from unittest.mock import MagicMock, patch, AsyncMock

from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()

@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.panel.convene_council_full")
@patch("agent.commands.panel.infer_story_id", return_value="TEST-123")
@patch("pathlib.Path.read_text", return_value="Dummy story content")
@patch("agent.commands.panel.context_loader.load_context", new_callable=AsyncMock)
@patch("subprocess.run")
def test_panel_run(mock_subproc, mock_ctx, mock_read, mock_infer, mock_convene, mock_sm):
    """
    Test that 'agent panel' calls convene_council_full with proper arguments
    and mode='consultative'.
    """
    # Mock secret manager as not initialized to bypass credential checks
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    # Mock subprocess git diff
    mock_run_return = MagicMock()
    mock_run_return.stdout = "file1.py\nfile2.py"
    mock_subproc.return_value = mock_run_return
    
    # Mock mock_convene return
    mock_convene.return_value = {"verdict": "PASS", "log_file": None, "json_report": {"story_id": "TEST-123", "overall_verdict": "PASS", "roles": []}}
    mock_ctx.return_value = {"rules": "", "instructions": "", "adrs": ""}

    with patch("agent.core.auth.decorators.validate_credentials"):
        result = runner.invoke(app, ["panel"])
    
    assert result.exit_code == 0
    assert "Convening the Governance Panel" in result.stdout
    
    # Verify the mode was "consultative"
    mock_convene.assert_called_once()
    call_args = mock_convene.call_args
    assert call_args.kwargs.get("mode") == "consultative"


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.panel.convene_council_full")
@patch("agent.commands.panel.infer_story_id", return_value="TEST-123")
@patch("pathlib.Path.read_text", return_value="Dummy story content")
@patch("agent.commands.panel.context_loader.load_context", new_callable=AsyncMock)
@patch("subprocess.run")
def test_panel_with_story_arg(mock_subproc, mock_ctx, mock_read, mock_infer, mock_convene, mock_sm):
    """Test 'agent panel MY-STORY' passes story_id correctly."""
    # Mock secret manager as not initialized to bypass credential checks
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_run_return = MagicMock()
    mock_run_return.stdout = "modified_file.py"
    mock_subproc.return_value = mock_run_return
    
    mock_convene.return_value = {"verdict": "PASS", "log_file": None, "json_report": {"story_id": "MY-STORY", "overall_verdict": "PASS", "roles": []}}
    mock_ctx.return_value = {"rules": "", "instructions": "", "adrs": ""}

    with patch("agent.core.auth.decorators.validate_credentials"):
        result = runner.invoke(app, ["panel", "MY-STORY"])
    
    assert result.exit_code == 0
    assert "MY-STORY" in result.stdout
    mock_convene.assert_called()


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.panel.infer_story_id", return_value=None)
@patch("agent.commands.panel.context_loader.load_context", new_callable=AsyncMock)
@patch("subprocess.run")
def test_panel_no_story_id_errors(mock_subproc, mock_ctx, mock_infer, mock_sm):
    """Test 'agent panel' with no story ID and no inference fails cleanly."""
    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_run_return = MagicMock()
    mock_run_return.stdout = ""
    mock_subproc.return_value = mock_run_return

    with patch("agent.core.auth.decorators.validate_credentials"):
        result = runner.invoke(app, ["panel"])

    assert result.exit_code == 1
    assert "Story ID is required" in result.stdout


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.panel.convene_council_full")
@patch("agent.commands.panel.infer_story_id", return_value="TEST-200")
@patch("agent.commands.panel.context_loader.load_context", new_callable=AsyncMock)
@patch("subprocess.run")
def test_panel_apply_blocks_invalid_runbook(mock_subproc, mock_ctx, mock_infer, mock_convene, mock_sm, tmp_path):
    """Panel --apply exits 1 and does NOT write when runbook validation fails."""
    from agent.core.config import config as real_config

    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_run_return = MagicMock()
    mock_run_return.stdout = "file1.py"
    mock_subproc.return_value = mock_run_return

    # Create a runbook file for the panel to find via rglob
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    runbook_file = runbook_dir / "TEST-200-runbook.md"
    original_content = "# Original Runbook Content\n## Implementation Steps\n"
    runbook_file.write_text(original_content)

    log_file = tmp_path / "governance-log.md"
    log_file.write_text("Panel advice text")

    mock_convene.return_value = {
        "verdict": "PASS",
        "log_file": log_file,
        "json_report": {"story_id": "TEST-200", "overall_verdict": "PASS", "roles": []},
    }
    mock_ctx.return_value = {"rules": "", "instructions": "", "adrs": ""}

    # AI returns content long enough to pass the >100 len check
    bad_content = "# Bad runbook\nNo steps here\n" + ("x" * 200)

    with patch("agent.core.auth.decorators.validate_credentials"), \
         patch.object(real_config, "runbooks_dir", runbook_dir), \
         patch.object(real_config, "stories_dir", tmp_path / "stories"), \
         patch("agent.core.ai.ai_service.get_completion", return_value=bad_content), \
         patch("agent.commands.panel.validate_runbook_schema", return_value=["Missing Implementation Steps"]):
        result = runner.invoke(app, ["panel", "TEST-200", "--apply"])

    assert result.exit_code == 1
    # File must NOT be overwritten
    assert runbook_file.read_text() == original_content


@patch("agent.core.auth.credentials.get_secret_manager")
@patch("agent.commands.panel.convene_council_full")
@patch("agent.commands.panel.infer_story_id", return_value="TEST-201")
@patch("agent.commands.panel.context_loader.load_context", new_callable=AsyncMock)
@patch("subprocess.run")
def test_panel_apply_writes_valid_runbook(mock_subproc, mock_ctx, mock_infer, mock_convene, mock_sm, tmp_path):
    """Panel --apply writes file when runbook validation passes."""
    from agent.core.config import config as real_config

    mock_sm.return_value.is_initialized.return_value = False
    mock_sm.return_value.is_unlocked.return_value = False

    mock_run_return = MagicMock()
    mock_run_return.stdout = "file1.py"
    mock_subproc.return_value = mock_run_return

    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    runbook_file = runbook_dir / "TEST-201-runbook.md"
    runbook_file.write_text("# Old content")

    log_file = tmp_path / "governance-log.md"
    log_file.write_text("Panel advice")

    mock_convene.return_value = {
        "verdict": "PASS",
        "log_file": log_file,
        "json_report": {"story_id": "TEST-201", "overall_verdict": "PASS", "roles": []},
    }
    mock_ctx.return_value = {"rules": "", "instructions": "", "adrs": ""}

    updated = "# Updated Runbook\n## Implementation Steps\n### Step 1\n" + ("x" * 200)

    with patch("agent.core.auth.decorators.validate_credentials"), \
         patch.object(real_config, "runbooks_dir", runbook_dir), \
         patch.object(real_config, "stories_dir", tmp_path / "stories"), \
         patch("agent.core.ai.ai_service.get_completion", return_value=updated), \
         patch("agent.commands.panel.validate_runbook_schema", return_value=[]):
        result = runner.invoke(app, ["panel", "TEST-201", "--apply"])

    assert result.exit_code == 0
    assert runbook_file.read_text() == updated
