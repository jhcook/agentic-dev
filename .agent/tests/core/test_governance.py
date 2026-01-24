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
from rich.console import Console

from agent.core.governance import convene_council_full


@pytest.fixture
def mock_ai_service():
    with patch("agent.core.governance.ai_service") as mock:
        mock.provider = "openai"
        yield mock

def test_governance_gatekeeper_block(mock_ai_service):
    """
    Test that in 'gatekeeper' mode, a 'BLOCK' verdict from AI results in a BLOCK return.
    """
    # Mock AI response to contain "Verdict: BLOCK"
    mock_ai_service.complete.return_value = "Verdict: BLOCK\nReason: Security violation."
    
    console = Console(quiet=True)
    
    verdict = convene_council_full(
        console=console,
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="gatekeeper"
    )
    
    assert verdict == "BLOCK"

def test_governance_gatekeeper_pass(mock_ai_service):
    """
    Test that in 'gatekeeper' mode, 'PASS' verdict returns PASS.
    """
    mock_ai_service.complete.return_value = "Verdict: PASS"
    
    console = Console(quiet=True)
    
    verdict = convene_council_full(
        console=console,
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="gatekeeper"
    )
    
    assert verdict == "PASS"

def test_governance_consultative_ignores_block(mock_ai_service):
    """
    Test that in 'consultative' mode, even if AI says 'BLOCK' (or negative sentiment),
    Logic does NOT return BLOCK (so CLI won't fail).
    """
    # Even if AI acts strict, the mode logic should prevent verdict=BLOCK
    mock_ai_service.complete.return_value = "Sentiment: NEGATIVE\nThis looks bad."
    
    console = Console(quiet=True)
    
    verdict = convene_council_full(
        console=console,
        story_id="TEST-1",
        story_content="Story",
        rules_content="Rules",
        instructions_content="Inst",
        full_diff="Diff",
        mode="consultative"
    )
    
    # In consultative mode, we usually default to PASS or just ignore block logic
    # The current implementation returns overall_verdict which defaults to "PASS"
    assert verdict == "PASS"
