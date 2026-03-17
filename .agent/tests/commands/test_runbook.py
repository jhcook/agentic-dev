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

from unittest.mock import patch, call

import pytest
import typer
from typer.testing import CliRunner

from agent.commands.runbook import new_runbook

runner = CliRunner()

# Valid runbook content that passes Pydantic schema validation AND code gates
VALID_RUNBOOK_CONTENT = '''# Runbook for INFRA-001

## Implementation Steps

### Step 1: Create the new module

#### [NEW] `new_module.py`

```python
"""New module with a proper docstring."""


def hello() -> str:
    """Return a greeting string."""
    return "world"
```
'''

# Invalid runbook content missing Implementation Steps section
INVALID_RUNBOOK_CONTENT = "Status: PROPOSED\n# Runbook without implementation steps"


@pytest.fixture
def app():
    test_app = typer.Typer()
    test_app.command()(new_runbook)
    return test_app

@pytest.fixture
def mock_fs(tmp_path):
    # Create template directory with runbook template
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "runbook-template.md").write_text("# Runbook Template\n## Plan\n<plan>")

    # Mock config paths
    with patch("agent.core.config.config.runbooks_dir", tmp_path / "runbooks"), \
         patch("agent.core.config.config.agent_dir", tmp_path / ".agent"), \
         patch("agent.core.config.config.stories_dir", tmp_path / "stories"), \
         patch("agent.core.config.config.templates_dir", templates_dir), \
         patch("agent.core.context.context_loader.load_context", return_value={"rules": "Rules", "agents": {"description": "", "checks": ""}, "instructions": "", "adrs": ""}), \
         patch("agent.core.auth.decorators.validate_credentials"):
        
        (tmp_path / "runbooks").mkdir()
        (tmp_path / ".agent").mkdir()
        (tmp_path / ".agent" / "workflows").mkdir()
        (tmp_path / "stories" / "INFRA").mkdir(parents=True)
        
        yield tmp_path

def test_new_runbook_success(mock_fs, app):
    """Valid AI output passes schema validation on first attempt."""
    story_id = "INFRA-001"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    with patch("agent.core.ai.ai_service.complete", return_value=VALID_RUNBOOK_CONTENT), \
         patch("agent.commands.runbook.upsert_artifact"):
         
        result = runner.invoke(app, [story_id])
        
        assert result.exit_code == 0
        assert "Runbook generated" in result.stdout
        assert (mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md").exists()

def test_new_runbook_not_committed(mock_fs, app):
    # Setup Draft Story
    story_id = "INFRA-002"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nOPEN\n# Story Content")
    
    result = runner.invoke(app, [story_id])
    
    assert result.exit_code == 1
    assert "is not COMMITTED" in result.stdout

def test_new_runbook_with_provider(mock_fs, app):
    """Provider flag is respected and valid runbook passes validation."""
    story_id = "INFRA-003"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    with patch("agent.core.ai.ai_service.set_provider") as mock_set_provider, \
         patch("agent.core.ai.ai_service.complete", return_value=VALID_RUNBOOK_CONTENT), \
         patch("agent.commands.runbook.upsert_artifact"):
        
        result = runner.invoke(app, [story_id, "--provider", "openai"])
        
        assert result.exit_code == 0
        mock_set_provider.assert_called_once_with("openai")

def test_new_runbook_retry_on_invalid_schema(mock_fs, app):
    """Invalid AI output triggers retry loop; exits code 1 after max attempts."""
    story_id = "INFRA-004"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    with patch("agent.core.ai.ai_service.complete", return_value=INVALID_RUNBOOK_CONTENT), \
         patch("agent.commands.runbook.upsert_artifact"):
        
        result = runner.invoke(app, [story_id])
        
        assert result.exit_code == 1
        assert "Schema validation failed after" in result.output

def test_new_runbook_self_corrects(mock_fs, app):
    """AI self-corrects on second attempt after initial schema failure."""
    story_id = "INFRA-005"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")
    
    # First call returns invalid, second returns valid
    with patch("agent.core.ai.ai_service.complete", side_effect=[INVALID_RUNBOOK_CONTENT, VALID_RUNBOOK_CONTENT]), \
         patch("agent.commands.runbook.upsert_artifact"):
        
        result = runner.invoke(app, [story_id])
        
        assert result.exit_code == 0
        assert "Attempt 1 failed schema validation" in result.stdout
        assert "Runbook generated" in result.stdout


def test_new_runbook_shows_formatted_errors(mock_fs, app):
    """Final failure displays formatted error output via format_runbook_errors."""
    story_id = "INFRA-006"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")

    with patch("agent.core.ai.ai_service.complete", return_value=INVALID_RUNBOOK_CONTENT), \
         patch("agent.commands.runbook.upsert_artifact"):

        result = runner.invoke(app, [story_id])

        assert result.exit_code == 1
        # Formatted errors should contain the schema validation header
        assert "SCHEMA VALIDATION FAILED" in result.output


def test_new_runbook_no_file_on_failure(mock_fs, app):
    """Runbook file must NOT be created when validation fails."""
    story_id = "INFRA-007"
    story_file = mock_fs / "stories" / "INFRA" / f"{story_id}.md"
    story_file.write_text("## State\nCOMMITTED\n# Story Content")

    with patch("agent.core.ai.ai_service.complete", return_value=INVALID_RUNBOOK_CONTENT), \
         patch("agent.commands.runbook.upsert_artifact"):

        result = runner.invoke(app, [story_id])

        assert result.exit_code == 1
        assert not (mock_fs / "runbooks" / "INFRA" / f"{story_id}-runbook.md").exists()
