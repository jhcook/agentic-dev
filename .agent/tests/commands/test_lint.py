import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from agent.commands.lint import lint
import typer

runner = CliRunner()

@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(lint)
    return test_app

@patch("agent.commands.lint.get_changed_files")
@patch("agent.commands.lint.run_ruff")
@patch("agent.commands.lint.run_shellcheck")
def test_lint_staged(mock_shellcheck, mock_ruff, mock_get_files, app):
    # Setup
    mock_get_files.return_value = ["file1.py", "script.sh"]
    mock_ruff.return_value = True
    mock_shellcheck.return_value = True
    
    result = runner.invoke(app) # Default is --staged=True
    
    assert result.exit_code == 0
    assert "Linting passed" in result.stdout
    
    # Verify calls
    mock_get_files.assert_called_with(base=None, staged_only=True)
    mock_ruff.assert_called_with(["file1.py"])
    mock_shellcheck.assert_called_with(["script.sh"])

@patch("agent.commands.lint.get_changed_files")
def test_lint_no_changes(mock_get_files, app):
    mock_get_files.return_value = []
    
    result = runner.invoke(app)
    
    assert result.exit_code == 0
    assert "No changed files" in result.stdout

@patch("pathlib.Path.rglob")
@patch("agent.commands.lint.run_ruff")
@patch("agent.commands.lint.run_shellcheck")
def test_lint_all(mock_shellcheck, mock_ruff, mock_rglob, app):
    # Mock file discovery
    # rglob returns iterators
    mock_rglob.side_effect = [
        [MagicMock(__str__=lambda x: "file1.py")], # .py files
        [MagicMock(__str__=lambda x: "agent")],    # agent binary
        [MagicMock(__str__=lambda x: "script.sh")] # .sh files
    ]
    mock_ruff.return_value = True
    mock_shellcheck.return_value = True
    
    # Mock exist check for .agent dir
    with patch("pathlib.Path.exists", return_value=True):
        result = runner.invoke(app, ["--all"])
        
    assert result.exit_code == 0
    assert "Linting all files" in result.stdout
