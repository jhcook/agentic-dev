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

"""test_runbook_infra_167 module."""

import pytest
from typer.testing import CliRunner
from agent.main import app
from unittest.mock import patch, MagicMock

runner = CliRunner()

def test_runbook_command_routing():
    """Verify that --legacy-gen flag routes to v1 logic vs chunked v2 logic."""
    # Mocking the generators imported in agent/commands/runbook.py
    with patch("agent.commands.runbook.generate_runbook_chunked") as mock_v2, \
         patch("agent.commands.runbook._run_monolithic_generation") as mock_v1, \
         patch("agent.commands.runbook._write_and_sync"):
        
        mock_v2.return_value = "# Runbook"
        mock_v1.return_value = "# Runbook"

        # 1. Test Default (V2)
        result = runner.invoke(app, ["new-runbook", "INFRA-167", "--force"])
        assert result.exit_code == 0
        mock_v2.assert_called_once()
        mock_v1.assert_not_called()

        mock_v2.reset_mock()
        mock_v1.reset_mock()

        # 2. Test Legacy Flag (V1)
        result = runner.invoke(app, ["new-runbook", "INFRA-167", "--legacy-gen", "--force"])
        assert result.exit_code == 0
        mock_v1.assert_called_once()
        mock_v2.assert_not_called()

def test_runbook_invalid_story_id():
    """Verify that an invalid Story ID format results in a proper CLI error."""
    result = runner.invoke(app, ["new-runbook", "INVALID_ID"])
    assert result.exit_code != 0
    assert "Story file not found for" in result.stdout
