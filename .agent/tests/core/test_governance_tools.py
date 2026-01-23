
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agent.core.governance import convene_council_full
from rich.console import Console

@pytest.fixture
def mock_ai_service():
    with patch("agent.core.governance.ai_service") as mock:
        mock.provider = "openai"
        mock.complete.return_value = "Verdict: PASS"
        mock.try_switch_provider.return_value = False
        yield mock

@pytest.fixture
def mock_config():
    with patch("agent.core.governance.config") as mock:
        mock.get_council_tools.return_value = ["github:get_issue"]
        yield mock

@pytest.fixture
def mock_executor():
    with patch("agent.core.engine.executor.AgentExecutor") as mock:
        mock_instance = AsyncMock()
        mock_instance.run.return_value = "Verdict: PASS"
        mock.return_value = mock_instance
        yield mock

@pytest.fixture
def mock_mcp_client():
    with patch("agent.core.mcp.client.MCPClient") as mock:
        yield mock

def test_convene_council_full_with_tools(mock_ai_service, mock_config, mock_executor, mock_mcp_client):
    console = Console()
    verdict = convene_council_full(
        console=console,
        story_id="TEST-123",
        story_content="Story content",
        rules_content="Rules content",
        instructions_content="Instructions",
        full_diff="diff content",
        council_identifier="preflight"
    )
    
    # Assert tools were requested
    mock_config.get_council_tools.assert_called_with("preflight")
    
    # Assert AgentExecutor was instantiated
    assert mock_executor.call_count > 0 # Once per role loop, but we mock roles too?
    # Actually roles are loaded from file or default. Default has 9 roles.
    # So executor should be called 9 times (or 9 instances created)
    
    # Assert run was called
    # Since we are mocking AgentExecutor class, return_value is the instance
    mock_executor.return_value.run.assert_awaited()
    
    assert verdict == "PASS"

def test_convene_council_full_no_tools(mock_ai_service, mock_config, mock_executor):
    mock_config.get_council_tools.return_value = []
    
    console = Console()
    verdict = convene_council_full(
        console=console,
        story_id="TEST-123",
        story_content="Story content",
        rules_content="Rules content",
        instructions_content="Instructions",
        full_diff="diff content",
        council_identifier="preflight"
    )
    
    # Assert tools requested
    mock_config.get_council_tools.assert_called_with("preflight")
    
    # Assert Executor NOT used
    mock_executor.assert_not_called()
    
    # Assert standard completion used
    assert mock_ai_service.complete.call_count > 0
    assert verdict == "PASS"
