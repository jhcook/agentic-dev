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

import yaml
from unittest.mock import patch
from agent.commands.implement import implement
import typer
from typer.testing import CliRunner

def test_implement_updates_journey_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Setup the mock environment
    from agent.core.config import config
    
    runner = CliRunner()
    test_app = typer.Typer()
    test_app.command()(implement)
    
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "INFRA").mkdir()
    story_file = mock_stories / "INFRA" / "INFRA-000-test.md"
    story_file.write_text(
        "# INFRA-000: Test\n\n## State\n\nDRAFT\n\n## Problem Statement\n\n"
        "## User Story\n\n## Acceptance Criteria\n\n## Non-Functional Requirements\n\n"
        "## Linked Journeys\n\n- JRN-001 (Test Journey)\n\n"
        "## Impact Analysis Summary\n\n## Test Strategy\n\n## Rollback Plan"
    )

    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    runbook_file = runbook_dir / "INFRA-000-runbook.md"
    runbook_file.write_text("Status: ACCEPTED\n# Runbook Content")
    
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "workflows").mkdir()
    
    journeys_dir = tmp_path / "journeys"
    journeys_dir.mkdir()
    (journeys_dir / "INFRA").mkdir()
    journey_file = journeys_dir / "INFRA" / "JRN-001-test.yaml"
    journey_file.write_text(
        "id: JRN-001\n"
        "state: COMMITTED\n"
        "implementation:\n"
        "  files: []\n"
        "  tests: []\n"
    )
    
    # We will simulate the `apply` parameter passing, which actually uses `apply_change_to_file`.
    # Wait, using `runner.invoke` goes through the entire command. We want to test the post-apply logic without actually hitting git or the LLM if possible, or we mock the LLM and `subprocess.run`
    
    # Let's mock the AI service to return a simple code block
    mock_llm_response = """
File: src/new_file.py
```python
print('Hello World')
```
File: tests/test_new_file.py
```python
def test_hello(): pass
```
"""
    
    # We will need the paths to exist so `p.exists()` returns True in `files_to_stage`
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    
    with patch.object(config, "runbooks_dir", runbook_dir), \
         patch.object(config, "agent_dir", agent_dir), \
         patch.object(config, "stories_dir", mock_stories), \
         patch.object(config, "journeys_dir", journeys_dir), \
         patch.object(config, "repo_root", tmp_path), \
         patch("agent.core.utils.load_governance_context", return_value="Rules"), \
         patch("agent.commands.implement.get_current_branch", return_value="INFRA-000/test"), \
         patch("agent.commands.implement.is_git_dirty", return_value=False), \
         patch("agent.commands.implement.extract_story_id", return_value="INFRA-000"), \
         patch("agent.commands.implement.create_branch"), \
         patch("agent.commands.implement.subprocess.run") as mock_run, \
         patch("agent.core.ai.ai_service.complete", return_value=mock_llm_response), \
         patch("agent.commands.implement.gates.run_security_scan") as mock_sec, \
         patch("agent.commands.implement.gates.run_qa_gate") as mock_qa, \
         patch("agent.commands.implement.gates.run_docs_check") as mock_docs:
         
        # Mock gates to pass
        from agent.commands.gates import GateResult
        mock_sec.return_value = GateResult("Security", True, 0.1, "")
        mock_qa.return_value = GateResult("QA", True, 0.1, "")
        mock_docs.return_value = GateResult("Docs", True, 0.1, "")

        # Run command with --yes and --apply to force immediate application
        result = runner.invoke(test_app, ["INFRA-000", "--apply", "--yes"])
        
        # After command completes, `src/new_file.py` and `tests/test_new_file.py` should exist
        # because `apply_change_to_file` writes them.
        assert result.exit_code == 0, result.stdout
        
        # Verify journey yaml was updated
        j_data = yaml.safe_load(journey_file.read_text())
        assert "src/new_file.py" in j_data["implementation"]["files"]
        assert "tests/test_new_file.py" in j_data["implementation"]["tests"]

        assert mock_run.called
