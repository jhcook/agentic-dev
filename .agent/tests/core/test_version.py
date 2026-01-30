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


import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from agent.main import app


class TestVersionCheck(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()




    @patch("agent.core.logger.configure_logging")
    @patch("subprocess.check_output")
    @patch("pathlib.Path")
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

    @patch("agent.core.logger.configure_logging")
    @patch("subprocess.check_output")
    @patch("pathlib.Path")
    def test_version_unknown_fallback(self, mock_path_cls, mock_subprocess, mock_logging):
        """Test fallback to default when both git and file fail."""
        # Git fails
        mock_subprocess.side_effect = Exception("Git not found")
        
        # Setup mock path chain
        mock_file_path = mock_path_cls.return_value.parent.parent.__truediv__.return_value
        mock_file_path.exists.return_value = False
        
        result = self.runner.invoke(app, ["--version"])
        self.assertIn("Agent CLI unknown", result.stdout)

if __name__ == '__main__':
    unittest.main()
