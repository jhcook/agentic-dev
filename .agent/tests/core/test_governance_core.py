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

from unittest.mock import patch, PropertyMock

import pytest

from agent.core.governance import convene_council_full


@pytest.fixture
def mock_ai_service():
    with patch("agent.core.config.Config.panel_engine", new_callable=PropertyMock) as mock_engine:
        mock_engine.return_value = "native"
        with patch("agent.core.governance.ai_service") as mock:
            mock.provider = "openai"
            yield mock

def test_governance_gatekeeper_block(mock_ai_service):
    """
    Test that in 'gatekeeper' mode, a 'BLOCK' verdict from AI results in a BLOCK return.
    """
    # Mock AI response to contain "Verdict: BLOCK" anchored to line start
    mock_ai_service.complete.return_value = "VERDICT: BLOCK\nReason: Security violation."
    
    result = convene_council_full(
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="gatekeeper"
    )
    
    assert result["verdict"] == "BLOCK"

def test_governance_gatekeeper_pass(mock_ai_service):
    """
    Test that in 'gatekeeper' mode, 'PASS' verdict returns PASS.
    """
    mock_ai_service.complete.return_value = "VERDICT: PASS"
    
    result = convene_council_full(
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="gatekeeper"
    )
    
    assert result["verdict"] == "PASS"

def test_governance_consultative_mode(mock_ai_service):
    """
    Test that in 'consultative' mode:
    1. Even if AI output contains "BLOCK", the overall verdict remains PASS.
    2. The raw findings are preserved.
    """
    # AI output that would normally block in gatekeeper mode
    ai_output = "I have some concerns about this design.\nVERDICT: BLOCK"
    mock_ai_service.complete.return_value = ai_output
    
    result = convene_council_full(
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="consultative"
    )
    
    # In consultative mode, we default to PASS
    assert result["verdict"] == "PASS"
    
    # Check that findings logic captured the output
    # The current implementation appends ALL reviews in consultative mode
    role_findings = result["json_report"]["roles"][0]["findings"]
    assert ai_output in role_findings
