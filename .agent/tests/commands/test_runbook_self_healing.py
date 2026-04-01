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

"""Integration tests for INFRA-155: new-runbook code gate self-healing loop.

Verifies that the self-healing mechanism in `new-runbook` detects code
violations (missing docstrings, trailing newlines) in AI-generated runbooks
and triggers a retry that produces clean output.

The code gate (`validate_code_block`) is patched to give precise control over
what errors/warnings are returned, isolating the retry-loop behaviour from the
gate internals already covered in `test_infra_155_gates.py`.
"""

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.runbook import new_runbook
from agent.core.implement.guards import ValidationResult

runner = CliRunner()

# Minimal runbook that satisfies schema validation — code gate result is mocked.
_RUNBOOK_TPL = '''\
# Runbook for {story_id}

## Implementation Steps

### Step 1: Add utility module

#### [NEW] `utils.py`

```python
"""Utility helpers."""


def helper() -> None:
    """No-op helper."""
    return None
```
'''


@pytest.fixture
def app() -> typer.Typer:
    """Create a Typer app instance with the new_runbook command."""
    test_app = typer.Typer()
    test_app.command()(new_runbook)
    return test_app


@pytest.fixture
def mock_fs(tmp_path):
    """Set up a temporary filesystem with the required directory structure."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "runbook-template.md").write_text(
        "# Runbook Template\n## Plan\n<plan>"
    )
    (templates_dir / "license_header.txt").write_text(
        "Copyright Mock\nLICENSE Mock"
    )

    with (
        patch("agent.core.config.config.runbooks_dir", tmp_path / "runbooks"),
        patch("agent.core.config.config.agent_dir", tmp_path / ".agent"),
        patch("agent.core.config.config.stories_dir", tmp_path / "stories"),
        patch("agent.core.config.config.templates_dir", templates_dir),
        patch(
            "agent.core.context.context_loader.load_context",
            return_value={
                "rules": "Rules",
                "agents": {"description": "", "checks": ""},
                "instructions": "",
                "adrs": "",
            },
        ),
        patch("agent.core.auth.decorators.validate_credentials"),
    ):
        (tmp_path / "runbooks").mkdir()
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "workflows").mkdir()
        (tmp_path / "stories" / "INFRA").mkdir(parents=True)

        yield tmp_path


def _make_gate_result(errors=None, warnings=None) -> ValidationResult:
    """Build a ValidationResult with given errors and warnings lists."""
    res = ValidationResult()
    res.errors = list(errors or [])
    res.warnings = list(warnings or [])
    return res


def test_code_gate_self_healing_success(mock_fs, app) -> None:
    """AI self-corrects code violations on retry; runbook is written after clean pass."""
    story_id = "INFRA-010"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")

    runbook_content = _RUNBOOK_TPL.format(story_id=story_id)
    gate_fail = _make_gate_result(errors=["utils.py: missing trailing newline"])
    gate_pass = _make_gate_result()

    with (
        patch("agent.core.ai.ai_service.complete", return_value=runbook_content),
        patch("agent.commands.runbook.upsert_artifact"),
        patch(
            "agent.commands.runbook_gates.validate_code_block",
            side_effect=[gate_fail, gate_pass],
        ),
    ):
        result = runner.invoke(app, [story_id, "--legacy-gen"])

        assert result.exit_code == 0, result.output
        assert "gate issue(" in result.stdout
        assert "Runbook generated" in result.stdout
        assert (mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md").exists()


def test_code_gate_exhausted_retries(mock_fs, app) -> None:
    """All retries return code-gate errors → exit code 1, no runbook file written."""
    story_id = "INFRA-011"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")

    runbook_content = _RUNBOOK_TPL.format(story_id=story_id)
    gate_fail = _make_gate_result(errors=["utils.py: missing docstring for helper()"])

    with (
        patch("agent.core.ai.ai_service.complete", return_value=runbook_content),
        patch("agent.commands.runbook.upsert_artifact"),
        patch("agent.commands.runbook_gates.validate_code_block", return_value=gate_fail),
    ):
        result = runner.invoke(app, [story_id, "--legacy-gen"])

        assert result.exit_code == 1
        assert "Gate corrections exhausted" in result.output
        assert not (mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md").exists()


def test_code_gate_warnings_non_blocking(mock_fs, app) -> None:
    """Warnings (e.g. nested function missing docstring) do not block generation."""
    story_id = "INFRA-012"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")

    runbook_content = _RUNBOOK_TPL.format(story_id=story_id)
    gate_warnings_only = _make_gate_result(
        warnings=["utils.py: nested function inner_no_doc() is missing a docstring"]
    )

    with (
        patch("agent.core.ai.ai_service.complete", return_value=runbook_content),
        patch("agent.commands.runbook.upsert_artifact"),
        patch(
            "agent.commands.runbook_gates.validate_code_block",
            return_value=gate_warnings_only,
        ),
    ):
        result = runner.invoke(app, [story_id, "--legacy-gen"])

        assert result.exit_code == 0, result.output
        assert "Runbook generated" in result.stdout
