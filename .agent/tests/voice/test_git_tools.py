import pytest
from unittest.mock import MagicMock, patch
from backend.voice.tools.git import git_stage_changes

@pytest.fixture(autouse=True)
def mock_otel():
    with patch('backend.voice.tools.git.logger') as mock_logger:
        yield mock_logger

def test_git_stage_all():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        
        result = git_stage_changes.invoke(input={"files": ["."]})
        
        assert "Staged all changes" in result
        mock_run.assert_called_with(
            ["git", "add", "."], 
            capture_output=True, 
            text=True, 
            check=True
        )

def test_git_stage_specific_file():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        
        result = git_stage_changes.invoke(input={"files": ["file1.py", "file2.py"]})
        
        assert "Staged: file1.py, file2.py" in result
        mock_run.assert_called_with(
            ["git", "add", "file1.py", "file2.py"], 
            capture_output=True, 
            text=True, 
            check=True
        )
