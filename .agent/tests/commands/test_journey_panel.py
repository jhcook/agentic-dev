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

"""Unit tests for INFRA-071: --panel flag on agent new-journey."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()


def test_panel_without_ai_errors():
    """AC Negative Test: --panel without --ai produces a clear error."""
    result = runner.invoke(app, ["new-journey", "JRN-999", "--panel"])
    assert result.exit_code != 0
    assert "--panel requires --ai" in result.output


@patch("agent.commands.journey.push_safe")
@patch("agent.commands.journey.upsert_artifact", return_value=True)
@patch("agent.commands.journey.Prompt.ask")
@patch("agent.commands.journey.IntPrompt.ask", return_value=4)
@patch("agent.commands.journey.config")
@patch("agent.core.governance.convene_council_full")
def test_panel_triggers_consultation(
    mock_convene, mock_config, mock_int_prompt,
    mock_prompt, mock_upsert, mock_push
):
    """AC1/AC3: --ai --panel triggers convene_council_full in consultative mode."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        scope_dir = tmpdir / "journeys" / "INFRA"
        scope_dir.mkdir(parents=True)
        templates_dir = tmpdir / "templates"
        templates_dir.mkdir()
        rules_dir = tmpdir / "rules"
        rules_dir.mkdir()
        instructions_dir = tmpdir / "instructions"
        instructions_dir.mkdir()
        repo_root = tmpdir
        tests_dir = repo_root / "tests" / "journeys"
        tests_dir.mkdir(parents=True)

        mock_config.journeys_dir = tmpdir / "journeys"
        mock_config.templates_dir = templates_dir
        mock_config.rules_dir = rules_dir
        mock_config.instructions_dir = instructions_dir
        mock_config.repo_root = repo_root

        # Mock prompt responses: title, AI description, test file linking
        mock_prompt.side_effect = [
            "Test Journey Title",
            "A test journey description",
            "",
        ]

        # Mock panel result
        mock_convene.return_value = {
            "verdict": "PASS",
            "json_report": {
                "roles": [
                    {"name": "Architect", "findings": ["Good structure"]},
                    {"name": "QA", "findings": []},
                ]
            },
        }

        with patch("agent.core.ai.ai_service") as mock_ai:
            mock_ai.complete.return_value = (
                "id: JRN-999\ntitle: Test\nactor: user\n"
                "description: test\nsteps:\n  - action: test\n"
                "    system_response: ok\n    assertions:\n      - works"
            )
            mock_ai.set_provider = MagicMock()

            result = runner.invoke(
                app,
                ["new-journey", "JRN-999", "--ai", "--panel", "--provider", "gemini"],
                catch_exceptions=False,
            )

        # Verify panel was called in consultative mode
        mock_convene.assert_called_once()
        call_kwargs = mock_convene.call_args
        assert call_kwargs.kwargs.get("mode") == "consultative"
