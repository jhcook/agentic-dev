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

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from agent.main import app

runner = CliRunner()

@pytest.fixture
def clean_env(tmp_path):
    # Setup - use tmp_path for all config directories
    mock_stories = tmp_path / "stories"
    mock_rules = tmp_path / "rules"
    mock_agent = tmp_path / "agent"
    
    mock_stories.mkdir()
    mock_rules.mkdir()
    mock_agent.mkdir()
    
    # Patch the config object instances in the loaded module
    with patch("agent.core.config.config.stories_dir", mock_stories), \
         patch("agent.core.config.config.rules_dir", mock_rules), \
         patch("agent.core.config.config.agent_dir", mock_agent):
    
        # Create fake story
        (mock_stories / "INFRA").mkdir()
        (mock_stories / "INFRA" / "INFRA-123-test.md").write_text("# Title\n\n## Problem Statement\n\n## User Story\n\n## Acceptance Criteria\n\n## Non-Functional Requirements\n\n## Impact Analysis Summary\n\n## Test Strategy\n\n## Rollback Plan")
        
        # Create fake rule
        (mock_rules / "test.mdc").write_text("Rule 1")
    
        yield

# We must patch where it is import/used
@patch("agent.core.governance.ai_service") 
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
@patch("agent.commands.check.scrub_sensitive_data")
def test_preflight_scrubbing_and_chunking(mock_scrub, mock_run, mock_check_ai, mock_gov_ai, clean_env):
    """
    Test that sensitive data is scrubbed and large diffs are chunked correctly.
    """
    # Mock AI Provider as GH (limited context -> forces chunking)
    mock_check_ai.provider = "gh"
    
    # Also ensure governance uses "gh" logic
    mock_gov_ai.provider = "gh"
    
    # Mock Subprocess (Git Diff)
    # Generate large diff > 6000 chars
    large_diff = "A" * 7000 
    mock_run.return_value.stdout = large_diff
    mock_run.return_value.returncode = 0
    
    # Mock Scrubbing
    mock_scrub.side_effect = lambda x: x.replace("A", "B") # Fake scrub
    
    # Mock AI Response
    mock_gov_ai.complete.return_value = "Verdict: PASS\nAnalysis: Looks good."
    
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai"])
    
    assert result.exit_code == 0
    assert "running preflight checks" in result.stdout.lower()
    
    # Verify Scrubbing was called
    mock_scrub.assert_called()
    # Verify call args on the GOVERNANCE ai service
    call_args = mock_gov_ai.complete.call_args_list[0]
    user_prompt = call_args[0][1]
    assert "BBBB" in user_prompt
    assert "AAAA" not in user_prompt
    
    # Verify Chunking happened
    # 7000 chars / 6000 chunk size = 2 chunks per role
    # With default roles, we expect many calls
    assert mock_gov_ai.complete.call_count > 6

@patch("agent.core.governance.ai_service")
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
def test_preflight_aggregation_block(mock_run, mock_check_ai, mock_gov_ai, clean_env):
    """
    Test that a single BLOCK verdict fails the entire command.
    """
    mock_check_ai.provider = "openai"
    mock_gov_ai.provider = "openai"
    
    mock_run.return_value.stdout = "diff content"
    mock_run.return_value.returncode = 0
    
    # Mock AI Response: First call returns BLOCK, others PASS (or loop stops)
    def side_effect(sys, user):
        if "Role: Architect" in sys or "Architect" in sys: 
            return "Verdict: PASS"
        if "Role: Security" in sys or "Security" in sys:
            return "Verdict: BLOCK\nReason: Hardcoded password."
        return "Verdict: PASS"
        
    mock_gov_ai.complete.side_effect = side_effect
    
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai"])
    
    assert result.exit_code == 1
    assert "Preflight Blocked by Governance Council" in result.stdout
    assert "Reason: Hardcoded password" in result.stdout

@patch("agent.core.governance.ai_service")
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
def test_preflight_audit_logging(mock_run, mock_check_ai, mock_gov_ai, clean_env):
    """
    Test that a log file is created after the run.
    """
    mock_check_ai.provider = "openai"
    mock_gov_ai.provider = "openai"
    
    mock_run.return_value.stdout = "diff"
    mock_run.return_value.returncode = 0

    mock_gov_ai.complete.return_value = "Verdict: PASS"
    
    # Run
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai"])
    
    assert result.exit_code == 0
    
    # Check log file in MOCKED agent dir (which is tmp_path / agent)
    from agent.core.config import config
    
    log_dir = config.agent_dir / "logs"
    assert log_dir.exists()
    
    # The code writes `governance-ID-TIMESTAMP.md`
    files = list(log_dir.glob("governance-INFRA-123-*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "Governance Preflight Report" in content
    assert "Story: INFRA-123" in content
    assert "PASS" in content

@patch("agent.core.governance.ai_service")
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
def test_preflight_verdict_parsing_false_positive(mock_run, mock_check_ai, mock_gov_ai, clean_env):
    """
    Test that mentions of 'BLOCK' in the text do not trigger a BLOCK verdict if the explicit verdict is PASS.
    """
    mock_check_ai.provider = "openai"
    mock_gov_ai.provider = "openai"
    mock_run.return_value.stdout = "diff"
    mock_run.return_value.returncode = 0
    
    # Review contains "BLOCK" but Verdict is PASS
    review_text = """Verdict: PASS
Analysis: This change is good. 
It avoids the error markdown for a BLOCK verdict.
"""
    mock_gov_ai.complete.return_value = review_text
    
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai"])
    
    assert result.exit_code == 0
    assert result.exit_code == 0
    assert "Preflight checks passed" in result.stdout

@patch("agent.core.governance.ai_service") 
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
def test_preflight_verdict_parsing_markdown_bold(mock_run, mock_check_ai, mock_gov_ai, clean_env):
    """
    Test that '**VERDICT: PASS**' is parsed correctly even if 'BLOCK' appears later.
    """
    mock_check_ai.provider = "openai"
    mock_gov_ai.provider = "openai"
    mock_run.return_value.stdout = "diff"
    mock_run.return_value.returncode = 0
    
    # Review matches the user report
    review_text = """**VERDICT: PASS**

### Brief analysis
* Verdict Aggregation: Validation that a single BLOCK from any role results in an overall exit code 1.
"""
    mock_gov_ai.complete.return_value = review_text
    
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai"])
    
    assert result.exit_code == 0
    assert "Preflight checks passed" in result.stdout

@patch("agent.core.governance.ai_service")
@patch("agent.commands.check.ai_service")
@patch("agent.commands.check.subprocess.run")
def test_preflight_json_report(mock_run, mock_check_ai, mock_gov_ai, clean_env, tmp_path):
    """
    Test that --report-file generates a valid JSON report.
    """
    mock_check_ai.provider = "openai"
    mock_gov_ai.provider = "openai"
    mock_run.return_value.stdout = "diff"
    mock_run.return_value.returncode = 0
    mock_gov_ai.complete.return_value = "Verdict: PASS"
    
    report_file = tmp_path / "report.json"
    
    # Run
    result = runner.invoke(app, ["preflight", "--story", "INFRA-123", "--ai", "--report-file", str(report_file)])
    
    assert result.exit_code == 0
    
    # Check JSON file
    assert report_file.exists()
    import json
    data = json.loads(report_file.read_text())
    
    assert data["story_id"] == "INFRA-123"
    assert data["overall_verdict"] == "PASS"
    assert len(data["roles"]) > 0
    assert data["roles"][0]["name"]
    assert data["roles"][0]["verdict"] == "PASS"
    
    # Check Output still contains human readable logs
    assert "Preflight checks passed" in result.stdout
