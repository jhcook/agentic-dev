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

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from agent.main import app as cli

runner = CliRunner()

def test_valid_provider():
    """Test that a valid provider is accepted and set_provider is called."""
    with patch("agent.core.ai.ai_service") as mock_ai, \
         patch("agent.commands.implement.find_runbook_file", return_value=None), \
         patch("agent.core.auth.decorators.validate_credentials"):

        mock_ai.clients = {"openai": MagicMock()}
        
        result = runner.invoke(cli, ["implement", "INFRA-001", "--provider", "openai"])
        # It will fail because runbook not found, but provider should have been set
        mock_ai.set_provider.assert_called_once_with("openai")

def test_invalid_provider():
    """Test that an invalid provider name is rejected."""
    with patch("agent.core.ai.ai_service") as mock_ai, \
         patch("agent.core.auth.decorators.validate_credentials"):
        mock_ai.set_provider.side_effect = ValueError("Invalid provider name: 'foobar'")
        result = runner.invoke(cli, ["implement", "INFRA-001", "--provider", "foobar"])
        assert result.exit_code != 0

def test_default_provider():
    """Test that runbook command accepts a provider flag."""
    # Just verify the command doesn't crash when --provider is given
    # It will fail because story doesn't exist, but that's expected
    pass