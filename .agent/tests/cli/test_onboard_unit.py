import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.onboard import (
    check_dependencies,
    ensure_agent_directory,
    ensure_gitignore,
    configure_api_keys,
    app as onboard_app,
)

# Fix for "AttributeError: 'Typer' object has no attribute 'name'"
# We use typer.testing.CliRunner which handles Typer apps correctly.
runner = CliRunner()


@patch("shutil.which")
def test_check_dependencies_success(mock_which):
    """Tests that check_dependencies passes when all binaries are found."""
    mock_which.return_value = "/usr/bin/some_path"
    try:
        check_dependencies()
    except typer.Exit:
        pytest.fail("check_dependencies raised Exit unexpectedly.")

    # Only 'git' is currently required in onboard.py
    assert mock_which.call_count >= 1
    mock_which.assert_any_call("git")


@patch("shutil.which")
def test_check_dependencies_failure(mock_which):
    """Tests that check_dependencies raises an error if a binary is missing."""
    mock_which.side_effect = lambda cmd: None if cmd == "git" else "/usr/bin/mock"
    
    with pytest.raises(typer.Exit) as excinfo:
        check_dependencies()
    assert excinfo.value.exit_code == 1


def test_ensure_agent_directory_success(tmp_path: Path):
    """Tests that ensure_agent_directory creates the .agent directory."""
    workspace_dir = tmp_path / ".agent"
    assert not workspace_dir.exists()
    ensure_agent_directory(tmp_path)
    assert workspace_dir.is_dir()


def test_ensure_agent_directory_is_file_error(tmp_path: Path):
    """Tests that ensure_agent_directory fails if .agent is a file."""
    workspace_file = tmp_path / ".agent"
    workspace_file.touch()
    with pytest.raises(typer.Exit) as excinfo:
        ensure_agent_directory(tmp_path)
    assert excinfo.value.exit_code == 1


def test_ensure_gitignore_creates_file(tmp_path: Path):
    """Tests that ensure_gitignore creates .gitignore if it's missing."""
    gitignore_path = tmp_path / ".gitignore"
    ensure_gitignore(tmp_path)
    assert gitignore_path.is_file()
    assert ".env" in gitignore_path.read_text()


def test_ensure_gitignore_appends_to_existing(tmp_path: Path):
    """Tests that ensure_gitignore appends .env to an existing file."""
    gitignore_path = tmp_path / ".gitignore"
    initial_content = "node_modules/\n"
    gitignore_path.write_text(initial_content)
    ensure_gitignore(tmp_path)
    final_content = gitignore_path.read_text()
    assert initial_content in final_content
    assert ".env" in final_content


def test_ensure_gitignore_does_not_duplicate(tmp_path: Path):
    """Tests that ensure_gitignore doesn't add .env if it already exists."""
    initial_content = "node_modules/\n.env\n"
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(initial_content)
    ensure_gitignore(tmp_path)
    assert gitignore_path.read_text() == initial_content


@patch("os.chmod")
@patch("getpass.getpass")
def test_configure_api_keys_creates_new(mock_getpass, mock_chmod, tmp_path: Path):
    """Tests creating a new .env file with user input."""
    # Mocks user entering keys in order
    mock_getpass.side_effect = ["test_openai_key"]
    
    env_path = tmp_path / ".env"
    
    configure_api_keys(tmp_path)

    assert env_path.is_file()
    content = env_path.read_text()
    # dotenv might use single quotes
    assert "OPENAI_API_KEY" in content
    assert "test_openai_key" in content
    mock_chmod.assert_called_with(env_path, 0o600)


@patch("os.chmod")
@patch("getpass.getpass")
def test_configure_api_keys_updates_partial(mock_getpass, mock_chmod, tmp_path: Path):
    """Tests updating a partially complete .env file."""
    mock_getpass.return_value = "new_key"
    env_path = tmp_path / ".env"
    # Pre-populate with nothing relevant or a different key if we had multiple
    env_path.write_text('OTHER_KEY="val"\n')

    configure_api_keys(tmp_path)

    mock_getpass.assert_called()
    content = env_path.read_text()
    assert "OPENAI_API_KEY" in content
    assert "new_key" in content
    mock_chmod.assert_called_with(env_path, 0o600)


@patch("os.chmod")
@patch("getpass.getpass")
def test_configure_api_keys_skips_if_complete(mock_getpass, mock_chmod, tmp_path: Path):
    """Tests that no input is requested if .env is complete."""
    env_path = tmp_path / ".env"
    env_path.write_text('OPENAI_API_KEY="key"\n')

    configure_api_keys(tmp_path)

    mock_getpass.assert_not_called()
    mock_chmod.assert_called()  # Permissions check still happens


# ================================
# Integration Tests for `onboard` Command
# ================================


@patch("shutil.which")
@patch("getpass.getpass")
def test_onboard_command_success_flow(mock_getpass, mock_which):
    """Tests the full `onboard` command in an ideal scenario."""
    mock_which.return_value = "/usr/bin/mock"
    mock_getpass.side_effect = ["test_openai_key"]

    with runner.isolated_filesystem() as fs:
        fs_path = Path(fs)
        # Invoke correctly using the Click command derived from Typer app
        result = runner.invoke(onboard_app, catch_exceptions=False)

        assert result.exit_code == 0
        assert "Onboarding complete!" in result.output

        # Verify filesystem state
        assert (fs_path / ".agent").is_dir()
        assert ".env" in (fs_path / ".gitignore").read_text()

        env_content = (fs_path / ".env").read_text()
        assert "OPENAI_API_KEY" in env_content
        assert "test_openai_key" in env_content

        if os.name == "posix":
            assert ((fs_path / ".env").stat().st_mode & 0o777) == 0o600


@patch("shutil.which")
def test_onboard_command_fails_on_missing_dependency(mock_which):
    """Tests that the `onboard` command fails if a dependency is missing."""
    mock_which.return_value = None  # Missing git

    with runner.isolated_filesystem():
        result = runner.invoke(onboard_app)
        assert result.exit_code != 0
        assert "Dependency not found" in result.output