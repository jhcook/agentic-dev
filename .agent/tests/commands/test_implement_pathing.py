import pytest
from unittest.mock import patch, MagicMock
from agent.commands.implement import apply_change_to_file, find_file_in_repo

@patch("agent.commands.implement.subprocess.check_output")
def test_find_file_in_repo(mock_subprocess):
    # Mock git output
    mock_subprocess.return_value = b"src/legacy/main.py\nsrc/agent/main.py"
    
    results = find_file_in_repo("main.py")
    assert "src/legacy/main.py" in results
    assert "src/agent/main.py" in results

@patch("agent.commands.implement.typer.confirm")
@patch("agent.commands.implement.console")
@patch("agent.commands.implement.find_file_in_repo")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.write_text")
@patch("pathlib.Path.mkdir")
def test_apply_auto_correct(mock_mkdir, mock_write, mock_exists, mock_find, mock_console, mock_confirm):
    # Scenario: AI tries to write to "main.py" (root), but it doesn't exist there.
    # It DOES exist at ".agent/src/agent/main.py"
    
    # 1. Root path does NOT exist
    mock_exists.return_value = False 
    
    # 2. Git search finds exactly one match
    mock_find.return_value = [".agent/src/agent/main.py"]
    
    # 3. Apply changes
    success = apply_change_to_file("main.py", "print('hello')", yes=True)
    
    # Assertions
    assert success is True
    # Verify we wrote to the DEEP path, not the root path
    # args[0] of write_text should be the content. The Path object it's called on matters.
    # We can check if console printed the auto-correct message
    mock_console.print.assert_any_call("[yellow]⚠️  Path Auto-Correct: 'main.py' -> '.agent/src/agent/main.py'[/yellow]")
