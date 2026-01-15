from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import typer
from typer.testing import CliRunner

from agent.commands.lint import lint

runner = CliRunner()

@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(lint)
    return test_app

@patch("agent.commands.lint.get_files_to_lint")
@patch("agent.commands.lint.run_ruff")
@patch("agent.commands.lint.run_shellcheck")
@patch("agent.commands.lint.run_eslint")
def test_lint_staged_default(mock_eslint, mock_shellcheck, mock_ruff, mock_get_files, app):
    # Setup
    mock_get_files.return_value = ["file1.py", "script.sh", "app.tsx"]
    mock_ruff.return_value = True
    mock_shellcheck.return_value = True
    mock_eslint.return_value = True
    
    result = runner.invoke(app) # Default is staged=True
    
    assert result.exit_code == 0
    assert "Linting passed" in result.stdout
    
    # Verify calls
    mock_get_files.assert_called_with(None, False, None, True)
    mock_ruff.assert_called_with(["file1.py"], fix=False)
    mock_shellcheck.assert_called_with(["script.sh"], fix=False)
    mock_eslint.assert_called_with(["app.tsx"], fix=False)

@patch("agent.commands.lint.get_files_to_lint")
def test_lint_no_changes(mock_get_files, app):
    mock_get_files.return_value = []
    
    result = runner.invoke(app)
    
    assert result.exit_code == 0
    assert "No files to lint" in result.stdout

@patch("agent.commands.lint.get_files_to_lint")
@patch("agent.commands.lint.run_ruff")
def test_lint_all(mock_ruff, mock_get_files, app):
    mock_get_files.return_value = ["file1.py"]
    mock_ruff.return_value = True
    
    result = runner.invoke(app, ["--all"])
    
    assert result.exit_code == 0
    mock_get_files.assert_called_with(None, True, None, True)

@patch("agent.commands.lint.get_files_to_lint")
@patch("agent.commands.lint.run_eslint")
def test_lint_path_fix(mock_eslint, mock_get_files, app):
    mock_get_files.return_value = ["web/file.ts"]
    mock_eslint.return_value = True
    
    result = runner.invoke(app, ["web/", "--fix"])
    
    assert result.exit_code == 0
    # Check that path arg is parsed correctly (typer converts to Path)
    # mock_get_files call args: path, all, base, staged
    args = mock_get_files.call_args[0]
    assert isinstance(args[0], Path)
    assert str(args[0]) == "web"
    assert args[1] is False # all
    
    mock_eslint.assert_called_with(["web/file.ts"], fix=True)
