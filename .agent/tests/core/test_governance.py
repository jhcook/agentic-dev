import pytest
from unittest.mock import patch, MagicMock
from agent.core.governance import convene_council_full
from rich.console import Console

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
