from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from agent.sync.cli import app

runner = CliRunner()

@pytest.fixture
def mock_sync_ops():
    with patch("agent.sync.cli.sync_ops") as mock:
        yield mock

def test_sync_pull(mock_sync_ops):
    result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    mock_sync_ops.sync.assert_called_once()

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

