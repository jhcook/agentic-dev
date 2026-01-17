
import unittest
from unittest.mock import patch, mock_open
from pathlib import Path
from typer.testing import CliRunner
from agent.main import app

class TestVersionCheck(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("agent.main.setup_logging")
    @patch("subprocess.check_output")
    def test_version_from_git(self, mock_subprocess, mock_logging):
        """Test that git version is returned when git command succeeds."""
        mock_subprocess.return_value = b"v1.2.3-git"
        result = self.runner.invoke(app, ["--version"])
        self.assertIn("Agent CLI v1.2.3-git", result.stdout)


    @patch("agent.main.setup_logging")
    @patch("subprocess.check_output")
    @patch("agent.main.Path")
    def test_version_from_file_fallback(self, mock_path_cls, mock_subprocess, mock_logging):
        """Test that file version is returned when git command fails."""
        # Git fails
        mock_subprocess.side_effect = Exception("Git not found")
        
        # Setup mock path chain
        # Path(__file__).parent.parent / "VERSION"
        mock_file_path = mock_path_cls.return_value.parent.parent.__truediv__.return_value
        mock_file_path.exists.return_value = True
        mock_file_path.read_text.return_value = "v1.2.3-file"
        
        result = self.runner.invoke(app, ["--version"])
        self.assertIn("Agent CLI v1.2.3-file", result.stdout)

    @patch("agent.main.setup_logging")
    @patch("subprocess.check_output")
    @patch("agent.main.Path")
    def test_version_unknown_fallback(self, mock_path_cls, mock_subprocess, mock_logging):
        """Test fallback to default when both git and file fail."""
        # Git fails
        mock_subprocess.side_effect = Exception("Git not found")
        
        # Setup mock path chain
        mock_file_path = mock_path_cls.return_value.parent.parent.__truediv__.return_value
        mock_file_path.exists.return_value = False
        
        result = self.runner.invoke(app, ["--version"])
        self.assertIn("Agent CLI v0.1.0", result.stdout)

if __name__ == '__main__':
    unittest.main()
