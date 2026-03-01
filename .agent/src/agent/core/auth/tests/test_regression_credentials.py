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

"""
Comprehensive regression tests for the credential validation system.

These tests guard against regressions where:
- Commands that DON'T need AI get blocked by missing LLM credentials
- The with_creds decorator is applied too broadly
- CI environments without API keys fail on non-AI commands
- Secret manager state (locked/unlocked/missing) causes unexpected failures
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError
from agent.core.auth.decorators import with_creds


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def clean_env():
    """Simulate CI: strip ALL credential env vars."""
    keys_to_strip = [
        "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GH_API_KEY", "GITHUB_TOKEN",
    ]
    env_overrides = {k: "" for k in keys_to_strip}
    # Use clear=False so other env vars (PATH, etc.) remain
    with patch.dict(os.environ, env_overrides):
        # Remove keys entirely (patch.dict with "" still sets them)
        for k in keys_to_strip:
            os.environ.pop(k, None)
        yield


@pytest.fixture
def mock_secret_manager_empty():
    """Secret manager exists but has no secrets (typical CI)."""
    with patch("agent.core.auth.credentials.get_secret_manager") as mock:
        manager = MagicMock()
        manager.is_unlocked.return_value = True
        manager.get_secret.return_value = None
        manager.is_initialized.return_value = False
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_secret_manager_locked():
    """Secret manager is initialized but locked."""
    with patch("agent.core.auth.credentials.get_secret_manager") as mock:
        manager = MagicMock()
        manager.is_unlocked.return_value = False
        manager.is_initialized.return_value = True
        manager._get_service_file.return_value = MagicMock(exists=lambda: False)
        mock.return_value = manager
        yield manager


@pytest.fixture(autouse=True)
def mock_ai_provider():
    """Ensure ai_service.provider is None so LLM_PROVIDER takes effect."""
    with patch("agent.core.ai.ai_service") as mock_ai:
        mock_ai.provider = None
        yield mock_ai


# =============================================================================
# REGRESSION: Credential validation per provider
# =============================================================================

class TestCredentialValidationPerProvider:
    """Ensure validate_credentials checks the RIGHT keys for each provider."""

    @pytest.mark.parametrize("provider,env_key,env_value", [
        ("openai", "OPENAI_API_KEY", "sk-test-key"),
        ("gemini", "GEMINI_API_KEY", "AIza-test"),
        ("gemini", "GOOGLE_API_KEY", "AIza-test-legacy"),
        ("anthropic", "ANTHROPIC_API_KEY", "sk-ant-test"),
        ("gh", "GITHUB_TOKEN", "ghp_test"),
        ("gh", "GH_API_KEY", "ghp_test2"),
    ])
    def test_passes_with_correct_env_var(self, clean_env, mock_secret_manager_empty, provider, env_key, env_value):
        """Each provider should pass when its correct env var is set."""
        with patch.dict(os.environ, {env_key: env_value}), \
             patch("agent.core.auth.credentials.LLM_PROVIDER", provider):
            validate_credentials(check_llm=True)  # Should NOT raise

    @pytest.mark.parametrize("provider,expected_key", [
        ("openai", "OPENAI_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("gh", "GH_API_KEY"),
    ])
    def test_fails_without_any_credential(self, clean_env, mock_secret_manager_empty, provider, expected_key):
        """Each provider should fail when no credential is available."""
        with patch("agent.core.auth.credentials.LLM_PROVIDER", provider):
            with pytest.raises(MissingCredentialsError) as exc:
                validate_credentials(check_llm=True)
            assert expected_key in str(exc.value)


class TestCredentialValidationSkip:
    """Ensure check_llm=False completely bypasses validation."""

    def test_skip_validation(self, clean_env, mock_secret_manager_empty):
        """check_llm=False should never raise, regardless of env state."""
        with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            validate_credentials(check_llm=False)  # Must not raise


class TestSecretManagerStates:
    """Test credential validation under various secret manager states."""

    def test_unlocked_with_secret(self, clean_env):
        """Passes when secret manager is unlocked and has the credential."""
        with patch("agent.core.auth.credentials.get_secret_manager") as mock_gsm:
            manager = MagicMock()
            manager.is_unlocked.return_value = True
            manager.get_secret.side_effect = lambda s, k: "secret-value" if s == "openai" and k == "api_key" else None
            mock_gsm.return_value = manager

            with patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
                validate_credentials(check_llm=True)  # Should pass

    def test_locked_no_service_file(self, clean_env, mock_secret_manager_locked):
        """Fails gracefully when locked and no service file exists."""
        with patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
            with pytest.raises(MissingCredentialsError):
                validate_credentials(check_llm=True)

    def test_uninitialized_no_env(self, clean_env, mock_secret_manager_empty):
        """Fails when manager is not initialized and env vars are empty."""
        with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            with pytest.raises(MissingCredentialsError):
                validate_credentials(check_llm=True)


# =============================================================================
# REGRESSION: with_creds decorator behavior
# =============================================================================

class TestWithCredsDecorator:
    """Ensure the with_creds decorator behaves correctly in isolation."""

    def test_blocks_when_no_credentials(self, clean_env, mock_secret_manager_empty):
        """Decorated function should raise typer.Exit when creds are missing."""
        from click.exceptions import Exit as ClickExit

        @with_creds
        def dummy_command():
            return "should not reach here"

        with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            with pytest.raises(ClickExit):
                dummy_command()

    def test_passes_through_when_credentials_present(self, clean_env, mock_secret_manager_empty):
        """Decorated function runs normally when credentials are available."""
        @with_creds
        def dummy_command():
            return "success"

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
             patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            result = dummy_command()
            assert result == "success"

    def test_check_llm_false_skips_validation(self, clean_env, mock_secret_manager_empty):
        """with_creds(check_llm=False) should never block."""
        @with_creds(check_llm=False)
        def dummy_command():
            return "success"

        with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            result = dummy_command()
            assert result == "success"

    def test_preserves_function_signature(self):
        """Decorator should preserve the wrapped function's name and docstring."""
        @with_creds
        def my_important_function():
            """Does important things."""
            pass

        assert my_important_function.__name__ == "my_important_function"
        assert "important" in my_important_function.__doc__


# =============================================================================
# REGRESSION: CLI registration correctness
#   These tests verify that commands are registered with the correct
#   credential requirements — preventing the exact regression that
#   prompted this test suite.
# =============================================================================

class TestCLICredentialRegistration:
    """
    Verify that main.py registers commands with appropriate credential guards.

    THIS IS THE CRITICAL REGRESSION TEST.
    Preflight should NOT be wrapped with with_creds because it only needs
    credentials when --ai is explicitly passed.
    """

    def test_preflight_not_wrapped_with_creds(self):
        """
        REGRESSION: preflight must NOT be wrapped in with_creds.
        It should only validate credentials when --ai is passed.
        
        If this test fails, it means someone re-added with_creds to preflight
        in main.py, which will break CI environments without API keys.
        """
        import agent.main as main_module

        # Read main.py source directly to check registration
        import inspect
        source = inspect.getsource(main_module)

        # The preflight registration should NOT include with_creds
        assert "with_creds(check.preflight)" not in source, (
            "REGRESSION DETECTED: preflight is wrapped with with_creds in main.py. "
            "This breaks CI environments without API keys. "
            "Preflight only needs credentials when --ai is passed."
        )

    def test_impact_requires_creds(self):
        """Impact analysis ALWAYS needs AI, so it MUST use with_creds."""
        import inspect
        import agent.main as main_module
        source = inspect.getsource(main_module)
        assert "with_creds(check.impact)" in source, (
            "impact command must be wrapped with with_creds — it always needs AI."
        )

    def test_panel_requires_creds(self):
        """Panel command ALWAYS needs AI, so it MUST use with_creds."""
        import inspect
        import agent.main as main_module
        source = inspect.getsource(main_module)
        assert "with_creds(check.panel)" in source, (
            "panel command must be wrapped with with_creds — it always needs AI."
        )


# =============================================================================
# REGRESSION: Preflight runs without AI credentials
#   Simulates the exact CI failure scenario.
# =============================================================================

class TestPreflightWithoutCreds:
    """
    Verify that preflight can run in CI-like environments without LLM keys.
    
    This directly tests the regression where `agent preflight` failed in
    GitHub Actions because GOOGLE_API_KEY was not set.
    """

    def test_preflight_no_ai_no_credentials_does_not_raise(self, clean_env, mock_secret_manager_empty):
        """
        REGRESSION: `agent preflight` (without --ai) must NOT fail
        due to missing LLM credentials.
        """
        from agent.commands.check import preflight
        import typer

        # Mock story validation and subprocess calls so we can focus on credential logic
        with patch("agent.commands.check.validate_story", return_value=True), \
             patch("agent.commands.check.subprocess") as mock_subprocess, \
             patch("agent.commands.check.infer_story_id", return_value="TEST-001"), \
             patch("agent.commands.check.config") as mock_config, \
             patch("agent.commands.check.context_loader") as mock_ctx, \
             patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):

            mock_config.stories_dir.rglob.return_value = []
            mock_ctx.load_context.return_value = {"rules": "", "instructions": "", "adrs": ""}

            # Simulate no staged changes
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.strip.return_value = ""
            mock_subprocess.run.return_value = mock_result

            # This should NOT raise MissingCredentialsError
            try:
                preflight(
                    story_id="TEST-001",
                    ai=False,
                    base=None,
                    provider=None,
                    report_file=None,
                    skip_tests=True,
                    ignore_tests=False,
                    interactive=False,
                )
            except typer.Exit:
                pass  # Exit is OK (no files to review), credential errors are NOT
            except MissingCredentialsError:
                pytest.fail(
                    "REGRESSION: preflight without --ai raised MissingCredentialsError. "
                    "This means credential validation is running when it shouldn't be."
                )

    def test_preflight_with_ai_requires_credentials(self, clean_env, mock_secret_manager_empty):
        """
        `agent preflight --ai` MUST validate credentials and fail
        if none are available.
        """
        from agent.commands.check import preflight

        with patch("agent.commands.check.validate_story", return_value=True), \
             patch("agent.commands.check.subprocess") as mock_subprocess, \
             patch("agent.commands.check.infer_story_id", return_value="TEST-001"), \
             patch("agent.commands.check.config") as mock_config, \
             patch("agent.commands.check.context_loader") as mock_ctx, \
             patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):

            mock_config.stories_dir.rglob.return_value = []
            mock_ctx.load_context.return_value = {"rules": "", "instructions": "", "adrs": ""}

            mock_result = MagicMock()
            mock_result.stdout = "some_file.py\n"
            mock_result.strip.return_value = "some_file.py"
            mock_subprocess.run.return_value = mock_result

            # Should EXIT (credential error) NOT succeed silently
            from click.exceptions import Exit as ClickExit
            with pytest.raises(ClickExit):
                preflight(
                    story_id="TEST-001",
                    ai=True,
                    base=None,
                    provider=None,
                    report_file=None,
                    skip_tests=True,
                    ignore_tests=False,
                    interactive=False,
                )


# =============================================================================
# REGRESSION: AIService._ensure_initialized credential handling
# =============================================================================

class TestAIServiceCredentials:
    """
    Verify that AIService handles credential failures gracefully,
    without polluting non-AI code paths.
    """

    def test_ai_service_not_initialized_at_import(self):
        """
        AIService should NOT call _ensure_initialized at import/construction time.
        This would break ALL imports of governance, check, etc.
        """
        from agent.core.ai.service import AIService
        service = AIService()
        assert service._initialized is False, (
            "AIService must not auto-initialize on construction — "
            "this would trigger credential checks at import time."
        )

    def test_ai_service_initializes_on_complete(self, clean_env, mock_secret_manager_empty):
        """
        AIService._ensure_initialized is called on first complete() call,
        which should trigger credential validation.
        """
        from agent.core.ai.service import AIService

        service = AIService()
        assert service._initialized is False

        with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
            # complete() triggers _ensure_initialized which triggers validate_credentials
            with pytest.raises(MissingCredentialsError):
                service.complete("system", "user")


# =============================================================================
# REGRESSION: Env var naming consistency across modules
#   Catches the exact bug where GOOGLE_API_KEY was renamed to GEMINI_API_KEY
#   but not all modules were updated.
# =============================================================================

class TestEnvVarNamingConsistency:
    """
    Verify that all modules agree on the canonical env var for each provider.
    
    THIS CATCHES THE EXACT REGRESSION: GOOGLE_API_KEY was renamed to
    GEMINI_API_KEY in service.py and config.py but credentials.py still
    had GOOGLE_API_KEY as the primary key.
    """

    def test_gemini_primary_key_is_gemini_api_key(self):
        """
        The PRIMARY env var for the gemini provider must be GEMINI_API_KEY
        across all modules. GOOGLE_API_KEY is only a backward-compat fallback.
        """
        # credentials.py: first item in list is the primary
        from agent.core.auth.credentials import validate_credentials
        import inspect
        source = inspect.getsource(validate_credentials)
        # The gemini entry should have GEMINI_API_KEY BEFORE GOOGLE_API_KEY
        gemini_idx = source.index('"gemini"')
        gemini_section = source[gemini_idx:gemini_idx + 100]
        gemini_pos = gemini_section.index("GEMINI_API_KEY")
        google_pos = gemini_section.index("GOOGLE_API_KEY")
        assert gemini_pos < google_pos, (
            "REGRESSION: In credentials.py, GEMINI_API_KEY must come BEFORE "
            "GOOGLE_API_KEY in the provider_key_map. GOOGLE_API_KEY is the "
            "legacy name kept only for backward compatibility."
        )

    def test_service_py_uses_gemini_api_key(self):
        """service.py must use GEMINI_API_KEY for the gemini provider."""
        from agent.core.ai import service as svc_module
        import inspect
        source = inspect.getsource(svc_module)
        assert '"GEMINI_API_KEY"' in source, (
            "service.py must reference GEMINI_API_KEY for the gemini provider."
        )

    def test_config_py_uses_gemini_api_key(self):
        """config.py provider config must use GEMINI_API_KEY."""
        from agent.core import config as cfg_module
        import inspect
        source = inspect.getsource(cfg_module.get_provider_config)
        assert '"GEMINI_API_KEY"' in source, (
            "config.py get_provider_config must reference GEMINI_API_KEY."
        )
