
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import typer
from typer.testing import CliRunner

# Add src to path if needed (though pytest usually handles this)
sys.path.append(str(Path.cwd() / "src"))

from agent.commands.onboard import app, onboard

runner = CliRunner()

@pytest.fixture
def mock_path_ensure():
    with patch("agent.commands.onboard.ensure_agent_directory") as m1, \
         patch("agent.commands.onboard.ensure_gitignore") as m2:
        yield m1, m2

@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which") as mock:
        yield mock

@pytest.fixture
def mock_getpass():
    with patch("getpass.getpass") as mock:
        yield mock

@pytest.fixture
def mock_dotenv():
    with patch("agent.commands.onboard.dotenv_values") as m1, \
         patch("agent.commands.onboard.set_key") as m2:
        m1.return_value = {} # Empty existing config
        yield m1, m2

@pytest.fixture
def mock_config(tmp_path):
    with patch("agent.commands.onboard.config") as mock:
        mock.etc_dir = tmp_path / "etc"
        mock.load_yaml.return_value = {}
        yield mock

@pytest.fixture
def mock_ai_service():
    with patch("agent.commands.onboard.ai_service") as mock, \
         patch("agent.commands.onboard.AIService") as mock_cls:
        
        # Setup mock behavior
        mock.clients = {"openai": MagicMock(), "gemini": MagicMock()}
        mock.get_available_models.return_value = [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"}
        ]
        
        # Mock verifying instance
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Hello World"
        mock_cls.return_value = mock_instance
        
        yield mock

@pytest.fixture
def test_app():
    test_app = typer.Typer()
    
    # Wrap the command to avoid metadata conflicts with the module-level app
    def wrapper():
        onboard()
        
    test_app.command(name="foo")(wrapper)
    return test_app

def test_onboard_dependencies_missing(test_app, mock_shutil_which):
    """Test that onboarding fails if critical dependencies are missing"""
    mock_shutil_which.side_effect = lambda x: None if x == "git" else "/usr/bin/python3"
    
    result = runner.invoke(test_app, [])
    if result.exit_code != 1:
        print(f"EXIT CODE: {result.exit_code}")
        print(f"OUTPUT: {result.output}")
        print(f"EXCEPTION: {result.exception}")
    assert result.exit_code == 1
    assert "Dependency not found: 'git'" in result.stdout

def test_onboard_happy_path(
    test_app,
    mock_shutil_which,
    mock_path_ensure, 
    mock_getpass, 
    mock_dotenv,
    mock_config,
    mock_ai_service
):
    """Test the full happy path of onboarding with prompts"""
    # 1. Deps found
    mock_shutil_which.return_value = "/usr/bin/tool"
    
    # 2. Getpass inputs for API Keys: OpenAI, Gemini, Anthropic
    # We provide values for all
    mock_getpass.side_effect = ["sk-openai", "sk-gemini", "sk-anthropic"]
    
    # 3. Typer Prompt for Provider Selection (select 1. openai)
    # 4. Typer Prompt for Model Selection (select 1. gpt-4o)
    # Using 'input=' to simulate stdin for prompts
    inputs = "1\n1\n" # Select OpenAI, Select Model 1
    
    with patch("agent.commands.onboard.typer.prompt", side_effect=["1", "1"]):
        result = runner.invoke(test_app, [])

    # Assertions
    assert result.exit_code == 0
    assert "[SUCCESS] Onboarding complete!" in result.stdout
    
    # Check API keys saved
    mock_set_key = mock_dotenv[1]
    assert mock_set_key.call_count == 3
    # Check we saved required keys
    calls = [
        call(str(Path(".").resolve() / ".env"), 'OPENAI_API_KEY', 'sk-openai'),
        call(str(Path(".").resolve() / ".env"), 'GEMINI_API_KEY', 'sk-gemini'),
        call(str(Path(".").resolve() / ".env"), 'ANTHROPIC_API_KEY', 'sk-anthropic')
    ]
    mock_set_key.assert_has_calls(calls, any_order=True)

    # Check Provider Configured
    mock_config.set_value.assert_any_call({}, "agent.provider", "openai")
    
    # Check Model Configured
    mock_config.set_value.assert_any_call({}, "agent.models.openai", "gpt-4o")

def test_onboard_skip_keys(
    test_app,
    mock_shutil_which, 
    mock_path_ensure, 
    mock_getpass, 
    mock_dotenv,
    mock_config,
    mock_ai_service
):
    """Test skipping optional keys"""
    mock_shutil_which.return_value = "/bin/tool"
    
    # User hits enter (empty) for all keys
    mock_getpass.return_value = ""
    
    # Select Provider (4. gh), Skip Model (enter)
    with patch("agent.commands.onboard.typer.prompt", side_effect=["4", ""]):
        result = runner.invoke(test_app, [])
        
    assert result.exit_code == 0
    # No keys should be saved
    mock_dotenv[1].assert_not_called()
    
    # Provider should be set to gh
    mock_config.set_value.assert_any_call({}, "agent.provider", "gh")

def test_verification_failure_warns(
    test_app,
    mock_shutil_which,
    mock_path_ensure, 
    mock_getpass, 
    mock_dotenv,
    mock_config,
    mock_ai_service
):
    """Test that verification failure just warns and doesn't crash"""
    mock_shutil_which.return_value = "/bin/tool"
    mock_getpass.return_value = "secret"
    
    # Mock AIService (instantiated inside verify) to fail
    with patch("agent.commands.onboard.AIService") as mock_cls_local:
        mock_inst = MagicMock()
        mock_inst.complete.side_effect = Exception("Connection Refused")
        mock_cls_local.return_value = mock_inst
        
        with patch("agent.commands.onboard.typer.prompt", side_effect=["1", "1"]):
             result = runner.invoke(test_app, [])
             
    assert result.exit_code == 0
    assert "[ERROR] Verification failed: Connection Refused" in result.stdout
    assert "[SUCCESS] Onboarding complete!" in result.stdout
