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

from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from agent.sync.cli import app

runner = CliRunner()

@pytest.fixture
def mock_sync_ops():
    with patch("agent.sync.cli.sync_ops") as mock_ops, \
         patch("agent.core.auth.decorators.validate_credentials"):
        yield mock_ops

def test_sync_pull(mock_sync_ops):
    result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    mock_sync_ops.pull.assert_called_once_with(verbose=False, backend=None, force=False, artifact_id=None, artifact_type=None)

def test_sync_push(mock_sync_ops):
    result = runner.invoke(app, ["push"])
    assert result.exit_code == 0
    mock_sync_ops.push.assert_called_once_with(verbose=False, backend=None, force=False, artifact_id=None, artifact_type=None)

def test_sync_status_default(mock_sync_ops):
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    mock_sync_ops.status.assert_called_once_with(detailed=False)

def test_sync_status_detailed(mock_sync_ops):
    result = runner.invoke(app, ["status", "--detailed"])
    assert result.exit_code == 0
    mock_sync_ops.status.assert_called_once_with(detailed=True)

def test_sync_delete_missing_id(mock_sync_ops):
    result = runner.invoke(app, ["delete"])
    assert result.exit_code != 0
    # Typer/Click prints usage on missing args
    assert "Usage" in result.output or "Missing argument" in result.output

def test_sync_delete_success(mock_sync_ops):
    result = runner.invoke(app, ["delete", "INFRA-001"])
    assert result.exit_code == 0
    mock_sync_ops.delete.assert_called_once_with("INFRA-001", None)

def test_sync_delete_with_type(mock_sync_ops):
    result = runner.invoke(app, ["delete", "INFRA-001", "--type", "story"])
    assert result.exit_code == 0
    mock_sync_ops.delete.assert_called_once_with("INFRA-001", "story")




def test_sync_pull_notion_backend(mock_sync_ops):
    """Verify that specifying --backend notion triggers the pull with the correct backend."""
    result = runner.invoke(app, ["pull", "--backend", "notion"])
    assert result.exit_code == 0
    mock_sync_ops.pull.assert_called_once_with(verbose=False, backend="notion", force=False, artifact_id=None, artifact_type=None)

@patch("agent.sync.cli.delete_artifact")
def test_sync_notebooklm_reset(mock_delete):
    """Verify that --reset deletes the notebooklm_state artifact."""
    mock_delete.return_value = True
    result = runner.invoke(app, ["notebooklm", "--reset"])
    assert result.exit_code == 0
    assert "Successfully reset NotebookLM sync state" in result.output
    mock_delete.assert_called_once_with("notebooklm_state", "state")

@patch("agent.sync.cli.delete_artifact")
def test_sync_notebooklm_flush(mock_delete):
    """Verify that --flush deletes the notebooklm_state artifact."""
    mock_delete.return_value = True
    result = runner.invoke(app, ["notebooklm", "--flush"])
    assert result.exit_code == 0
    assert "Successfully reset NotebookLM sync state" in result.output
    mock_delete.assert_called_once_with("notebooklm_state", "state")

def test_sync_notebooklm_no_flags():
    """Verify that notebooklm without flags prints help."""
    result = runner.invoke(app, ["notebooklm"])
    assert result.exit_code == 0
    assert "Use --reset or --flush" in result.output
