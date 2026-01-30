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

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

# Add src to path if needed (though pytest usually handles this)
sys.path.append(str(Path.cwd() / "src"))

from agent.commands.onboard import (
    onboard,
    app as onboard_app,
    check_dependencies,
    configure_api_keys,
    ensure_agent_directory,
    ensure_gitignore,
)

runner = CliRunner()

@pytest.fixture
def mock_runner():
    return runner

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
def mock_subprocess_run():
    with patch("agent.commands.onboard.subprocess.run") as mock:
        yield mock

@pytest.fixture
def mock_check_dependencies():
    with patch("agent.commands.onboard.check_dependencies") as mock:
        yield mock

@pytest.fixture
def mock_user_input():
    with patch("agent.commands.onboard.getpass.getpass") as mock_pass, \
         patch("agent.commands.onboard.typer.prompt") as mock_prompt:
             
        # Create a combined side_effect handler or mock object
        # But the tests treat mock_user_input as a single mock with side_effect
        # This is tricky if it covers both getpass and prompt.
        # In the test logic: 
        # mock_user_input.side_effect = [...]
        # The test seems to expect a single mock callable that handles input.
        # But onboard.py calls getpass.getpass AND typer.prompt.
        
        # Let's check how the previous test version did it.
        # It had `mock_getpass` and patch logic for `typer.prompt`.
        
        # I'll revert to separate mocks if possible, or implement a unifying fixture.
        # Given the test code: `mock_user_input.side_effect = [...]`
        # and checking the sequence of calls: getpass, getpass, getpass, prompt, prompt.
        
        # I will create a wrapper mock that feeds both.
        
        mock_wrapper = MagicMock()
        
        def side_effect(*args, **kwargs):
            return mock_wrapper()
            
        mock_pass.side_effect = side_effect
        mock_prompt.side_effect = side_effect
        
        yield mock_wrapper

@pytest.fixture
def mock_github_auth():
    with patch("agent.commands.onboard.check_github_auth") as mock:
        yield mock

@pytest.fixture
def test_app():
    test_app = typer.Typer()
    
    # Wrap the command to avoid metadata conflicts with the module-level app
    def wrapper():
        onboard()
        
    test_app.command(name="foo")(wrapper)
    return test_app

@pytest.fixture
def mock_onboard_steps():
    with patch("agent.commands.onboard.configure_voice_settings") as m1, \
         patch("agent.commands.onboard.setup_frontend") as m2:
        yield m1, m2

def test_onboard_dependencies_missing(test_app, mock_shutil_which):

    """Test that onboarding fails if critical dependencies are missing"""
    mock_shutil_which.side_effect = lambda x: None if x == "git" else "/usr/bin/python3"
    
    result = runner.invoke(test_app, [])
    if result.exit_code != 1:
        print(f"EXIT CODE: {result.exit_code}")
        print(f"OUTPUT: {result.output}")
        print(f"EXCEPTION: {result.exception}")
    assert result.exit_code == 1
    assert "Binary dependency not found" in result.stdout

@pytest.fixture
def mock_secret_manager():
    with patch("agent.commands.onboard.get_secret_manager") as mock1, \
         patch("agent.core.secrets.get_secret_manager") as mock2:
        manager = MagicMock()
        mock1.return_value = manager
        mock2.return_value = manager
        
        manager.is_initialized.return_value = True
        manager.is_unlocked.return_value = True
        manager.get_secret.return_value = None # No existing secrets
        manager.has_secret.return_value = False # Default to not having secret
        yield manager

@pytest.fixture(autouse=True)
def mock_env():
    """Ensure clean environment for all tests."""
    with patch.dict("os.environ", {}, clear=True):
        # Restore PATH so mocks (shutil.which) might work if they relied on real path, 
        # but here we utilize side_effects usually.
        # However, to be safe, maybe keep PATH or crucial vars?
        # Actually simplest is clear=True.
        yield

@pytest.fixture
def mock_prompt_password():
    with patch("agent.commands.secret._prompt_password") as mock:
        mock.return_value = "Secret123!"
        yield mock

@pytest.fixture
def mock_validate_password():
    with patch("agent.commands.secret._validate_password_strength") as mock:
        mock.return_value = True
        yield mock

def test_onboard_happy_path(
    test_app, 
    mock_check_dependencies, 
    mock_user_input, 
    mock_runner, 
    mock_config, 
    mock_ai_service,
    mock_github_auth,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_onboard_steps,
):
    """Test the happy path where all checks pass and user provides keys."""
    # Simulate user input:
    # 1. OpenAI Key
    # 2. Gemini Key
    # 3. Anthropic Key
    # 4. Default Provider Selection (1=openai, 2=gemini etc. logic changed to
    #    list index)
    #    PROVIDERS keys list order: openai, gemini, anthropic, gh. 
    #    Selection: "2" -> gemini.
    # 5. Default Model Selection (Enter to skip/default)
    mock_user_input.side_effect = [
        "sk-openai",    # OpenAI Key
        "sk-gemini",    # Gemini Key
        "sk-anthropic", # Anthropic Key
        "2",            # Select Gemini
        "1",            # Select Model (1st in list)
    ]

    result = mock_runner.invoke(test_app, [])
    
    # Print output for debugging if it fails
    if result.exit_code != 0:
        print(result.stdout)
        print(result.exception)

    assert result.exit_code == 0
    assert "Agent Onboarding" in result.stdout
    mock_check_dependencies.assert_called_once()
    mock_github_auth.assert_called_once()
    
    # Check Secret Manager calls
    # Should be initialized (or checked) and unlocked
    # In this test, is_initialized=True, is_unlocked=True
    
    # Verify set_secret calls
    # Arguments: service, key, value
    mock_secret_manager.set_secret.assert_any_call("openai", "api_key", "sk-openai")
    mock_secret_manager.set_secret.assert_any_call("gemini", "api_key", "sk-gemini")
    mock_secret_manager.set_secret.assert_any_call(
        "anthropic", "api_key", "sk-anthropic"
    )

    # Check Provider Configured
    # We selected "2" (Gemini)
    mock_config.set_value.assert_any_call({}, "agent.provider", "gemini")
    
    # Check Model Configured
    # We selected "1" -> models[0]['id'] -> "gpt-4o"
    mock_config.set_value.assert_any_call({}, "agent.models.gemini", "gpt-4o")

def test_onboard_skip_keys(
    test_app,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_shutil_which,
    mock_check_dependencies,
    mock_user_input,
    mock_runner,
    mock_config,
    mock_ai_service,
    mock_github_auth,
    mock_onboard_steps,
):
    """Test skipping optional keys"""
    mock_shutil_which.return_value = "/bin/tool"
    
    # User hits enter (empty) for all keys (3 keys)
    # Select Provider (4. gh)
    # Select Model (enter to skip)
    mock_user_input.side_effect = ["", "", "", "4", ""]
    
    result = mock_runner.invoke(test_app, [])
        
    assert result.exit_code == 0
    # No keys should be saved
    mock_secret_manager.set_secret.assert_not_called()
    
    # Provider should be set to gh
    mock_config.set_value.assert_any_call({}, "agent.provider", "gh")

def test_verification_failure_warns(
    test_app,
    mock_shutil_which,
    mock_path_ensure, 
    mock_user_input,
    mock_runner, 
    mock_config, 
    mock_ai_service,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_github_auth,
    mock_onboard_steps,
):
    """Test that verification failure just warns and doesn't crash"""
    mock_shutil_which.return_value = "/bin/tool"
    # Inputs handled by side_effect in assertion block

    
    # Mock AIService (instantiated inside verify) to fail
    with patch("agent.commands.onboard.AIService") as mock_cls_local:
        mock_inst = MagicMock()
        mock_inst.complete.side_effect = Exception("Connection Refused")
        mock_cls_local.return_value = mock_inst
        
        # Inputs: 3 keys (skipping), Select Provider 1, Select Model 1
        mock_user_input.side_effect = ["", "", "", "1", "1"]
        result = mock_runner.invoke(test_app, [])
             
    assert result.exit_code == 0
    assert "[ERROR] Verification failed: Connection Refused" in result.stdout
    assert "[SUCCESS] Onboarding complete!" in result.stdout

def test_check_github_auth_authenticated(
    test_app,
    mock_shutil_which,
    mock_subprocess_run,
    mock_path_ensure, 
    mock_user_input, 
    mock_runner,
    mock_config,
    mock_ai_service,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_onboard_steps,
):
    """Test standard flow when gh is authenticated"""
    mock_shutil_which.return_value = "/usr/bin/tool"
    
    # Mock gh auth status success
    mock_subprocess_run.return_value.returncode = 0
    
    # Mock secret existing
    mock_secret_manager.has_secret.return_value = True

    # Standard inputs
    # 3 Keys (skip), Provider 1, Model 1
    mock_user_input.side_effect = ["", "", "", "1", "1"]
    
    with patch("agent.commands.onboard.typer.confirm", return_value=False):
        result = mock_runner.invoke(test_app, [])
        
    assert result.exit_code == 0
    assert "Configuring GitHub Access..." in result.stdout
    assert "GitHub access already configured" in result.stdout

def test_check_github_auth_not_authenticated_yes(
    test_app,
    mock_shutil_which,
    mock_subprocess_run,
    mock_path_ensure, 
    mock_user_input, 
    mock_runner,
    mock_config,
    mock_ai_service,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_onboard_steps,
):
    """Test flow when gh is NOT authenticated and user says YES to login"""
    mock_shutil_which.return_value = "/usr/bin/tool"
    
    # Mock gh auth status failure
    mock_subprocess_run.return_value.returncode = 1
    
    # Standard inputs + YES to login
    # 3 Keys (skip), Provider 1, Model 1
    # Note: explicit confirm mock handles the "Yes" to login,
    # so we don't need input for that?
    # Typer confirm usually uses stdin? Or uses typer.confirm?
    # We patch typer.confirm below.
    # So we just need the standard flow inputs.
    mock_user_input.side_effect = ["", "", "", "dummy_token", "1", "1"]
    
    # We also need to mock subprocess.Popen for the login attempt
    with patch("agent.commands.onboard.subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Logged in", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        with patch("agent.commands.onboard.typer.confirm", return_value=True):
            result = mock_runner.invoke(test_app, [])
    
    assert result.exit_code == 0
    # Steps:
    # 1. Configuring -> 2. We will now configure -> 3. GitHub CLI authenticated
    assert "We will now configure GitHub access" in result.stdout
    assert "GitHub CLI authenticated" in result.stdout
    # Check we called login
    mock_popen.assert_called_with(
        ["gh", "auth", "login", "--with-token"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def test_verification_uses_configured_provider(
    test_app,
    mock_shutil_which,
    mock_path_ensure, 
    mock_user_input, 
    mock_runner, 
    mock_config,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_github_auth,
    mock_onboard_steps,
):
    """Test that verification forces the configured provider"""
    mock_shutil_which.return_value = "/bin/tool"
    
    # Mock config to return 'gemini' as provider
    # Mocking get_value is tricky because it's a method on the real Config object,
    # but mock_config fixture patches the module-level 'config' INSTANCE in onboard.py?
    # No, fixture `mock_config` patches "agent.commands.onboard.config".
    
    # We need to ensure load_yaml returns data that get_value can read, 
    # OR mock get_value directly.
    # The code calls:
    #   config_data = config.load_yaml(...)
    #   configured_provider = config.get_value(config_data, "agent.provider")
    
    mock_config.load_yaml.return_value = {"agent": {"provider": "gemini"}}
    # If config.get_value is NOT mocked on the object, it runs real logic?
    # mock_config is a MagicMock replacing the `config` object.
    # So `config.get_value` is also a mock.
    mock_config.get_value.return_value = "gemini" 

    # Mock AIService to verify set_provider call
    with patch("agent.commands.onboard.AIService") as mock_cls_local:
        mock_inst = MagicMock()
        mock_inst.clients = {"gemini": "client"} # Ensure gemini is considered available
        mock_inst.complete.return_value = "Hello World"
        mock_cls_local.return_value = mock_inst

        # Inputs: 3 keys (skipping), Select Provider 2 (Gemini), Select Model 1
        mock_user_input.side_effect = ["", "", "", "2", "1"]
        result = mock_runner.invoke(test_app, [])
        
        # Verify set_provider was called with gemini
        mock_inst.set_provider.assert_called_with("gemini")
        
    assert result.exit_code == 0

def test_onboard_migration(
    test_app,
    mock_shutil_which,
    mock_user_input,
    mock_runner,
    mock_config,
    mock_secret_manager,
    mock_prompt_password,
    mock_validate_password,
    mock_ai_service,
    mock_github_auth,
    mock_onboard_steps,
):
    """Test migration of keys from env to secret manager."""
    mock_shutil_which.return_value = "/bin/tool"
    
    # Setup: 
    # SecretManager is initialized/unlocked but empty
    
    # Set Environment Variable for Gemini to trigger migration
    # And mock manager.get_secret to return None for it
    
    with patch.dict("os.environ", {"GEMINI_API_KEY": "env_gemini_key"}):
        
        # Mock manager.get_secret specifically
        # (service, key)
        def manager_get_secret_side_effect(service, key):
            if service == "openai":
                return "stored_openai_key"
            return None
            
        # Mock manager.has_secret
        def manager_has_secret_side_effect(service, key):
            if service == "openai":
                return True
            return False

        mock_secret_manager.get_secret.side_effect = manager_get_secret_side_effect
        mock_secret_manager.has_secret.side_effect = manager_has_secret_side_effect
    
        # User Inputs:
        # 1. Migration Confirmation for Gemini (Yes) -> handled by typer.confirm patch?
        # 2. Anthropic Input (Skip) -> handled by mock_user_input returning ""
        # 3. Provider Selection (1)
        # 4. Model Selection (1)
        
        # Note regarding confirm: 
        # The code uses `typer.confirm`. We need to patch it to say Yes.
        
        # Anthropic skip, Provider 1, Model 1
        mock_user_input.side_effect = ["", "1", "1"]
        
        with patch("agent.commands.onboard.typer.confirm", return_value=True):
            result = mock_runner.invoke(test_app, [])
            
        assert result.exit_code == 0
        
        # OpenAI: Already configured
        # Gemini: Migrated
        # Anthropic: Skipped
        assert "[WARN] Google Gemini key found in environment" in result.stdout
        assert "[OK] Migrated Google Gemini key" in result.stdout
        
        # assertions
        mock_secret_manager.set_secret.assert_any_call(
            "gemini", "api_key", "env_gemini_key"
        )
