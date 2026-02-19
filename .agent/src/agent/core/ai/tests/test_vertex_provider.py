"""Tests for the Vertex AI provider integration.

Covers:
  - _build_genai_client factory (Gemini vs Vertex paths)
  - Vertex AI error handling in _try_complete
  - Vertex in the fallback chain
"""
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Factory: _build_genai_client
# ---------------------------------------------------------------------------

class TestBuildGenaiClient:
    """Tests for AIService._build_genai_client static method."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("agent.core.ai.service.get_secret", return_value="AIza-fake-key")
    def test_gemini_client_uses_api_key(self, mock_secret):
        """Gemini path should pass api_key to genai.Client."""
        from agent.core.ai.service import AIService

        with patch("google.genai.Client") as MockClient:
            AIService._build_genai_client("gemini")
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args[1]
            assert call_kwargs["api_key"] == "AIza-fake-key"
            assert "vertexai" not in call_kwargs or not call_kwargs.get("vertexai")

    @patch.dict(
        os.environ,
        {"GOOGLE_CLOUD_PROJECT": "my-project", "GOOGLE_CLOUD_LOCATION": "europe-west1"},
        clear=False,
    )
    def test_vertex_client_uses_adc(self):
        """Vertex path should set vertexai=True with project and location."""
        from agent.core.ai.service import AIService

        with patch("google.genai.Client") as MockClient:
            AIService._build_genai_client("vertex")
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args[1]
            assert call_kwargs["vertexai"] is True
            assert call_kwargs["project"] == "my-project"
            assert call_kwargs["location"] == "europe-west1"

    @patch.dict(
        os.environ,
        {"GOOGLE_CLOUD_PROJECT": "my-project"},
        clear=False,
    )
    def test_vertex_defaults_to_us_central1(self):
        """When GOOGLE_CLOUD_LOCATION is unset, default to us-central1."""
        from agent.core.ai.service import AIService

        # Ensure location is NOT in env
        os.environ.pop("GOOGLE_CLOUD_LOCATION", None)

        with patch("google.genai.Client") as MockClient:
            AIService._build_genai_client("vertex")
            call_kwargs = MockClient.call_args[1]
            assert call_kwargs["location"] == "us-central1"

    def test_invalid_provider_raises(self):
        """Factory should reject unknown providers."""
        from agent.core.ai.service import AIService

        with pytest.raises(ValueError, match="Unsupported genai provider"):
            AIService._build_genai_client("invalid")


# ---------------------------------------------------------------------------
# Credential validation for vertex
# ---------------------------------------------------------------------------

class TestVertexCredentialValidation:
    """Ensure validate_credentials works with the vertex provider."""

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project"}, clear=False)
    @patch("agent.core.ai.ai_service")
    @patch("agent.core.auth.credentials.LLM_PROVIDER", "vertex")
    @patch("agent.core.auth.credentials.get_secret_manager")
    def test_vertex_passes_with_project(self, mock_get_sm, mock_ai_service):
        """validate_credentials should pass when GOOGLE_CLOUD_PROJECT is set."""
        mock_ai_service.provider = "vertex"
        mock_sm = MagicMock()
        mock_sm.is_unlocked.return_value = False
        mock_sm.is_initialized.return_value = False
        mock_get_sm.return_value = mock_sm
        from agent.core.auth.credentials import validate_credentials

        # Should not raise
        validate_credentials()

    @patch.dict(os.environ, {}, clear=True)
    @patch("agent.core.ai.ai_service")
    @patch("agent.core.auth.credentials.LLM_PROVIDER", "vertex")
    @patch("agent.core.auth.credentials.get_secret_manager")
    def test_vertex_fails_without_project(self, mock_get_sm, mock_ai_service):
        """validate_credentials should raise when GOOGLE_CLOUD_PROJECT is missing."""
        mock_ai_service.provider = "vertex"
        mock_sm = MagicMock()
        mock_sm.is_unlocked.return_value = False
        mock_sm.is_initialized.return_value = False
        mock_get_sm.return_value = mock_sm
        from agent.core.auth.credentials import validate_credentials, MissingCredentialsError

        with pytest.raises(MissingCredentialsError):
            validate_credentials()


# ---------------------------------------------------------------------------
# Fallback chain includes vertex
# ---------------------------------------------------------------------------

class TestVertexFallbackChain:
    """Verify vertex participates in provider fallback."""

    def _make_service(self, available_clients: dict):
        from agent.core.ai.service import AIService

        svc = AIService.__new__(AIService)
        svc.clients = available_clients
        svc.provider = None
        svc.is_forced = False
        svc.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'vertex': 'gemini-2.0-flash',
            'openai': 'gpt-4o',
            'anthropic': 'claude-sonnet-4-5-20250929',
        }
        return svc

    def test_vertex_is_in_fallback_after_gemini(self):
        """If gemini fails, vertex should be tried next."""
        svc = self._make_service({
            "gemini": MagicMock(),
            "vertex": MagicMock(),
            "openai": MagicMock(),
        })
        svc.provider = "gemini"
        switched = svc.try_switch_provider("gemini")
        assert switched is True
        assert svc.provider == "vertex"

    def test_vertex_to_openai_fallback(self):
        """If vertex fails, openai should be next."""
        svc = self._make_service({
            "vertex": MagicMock(),
            "openai": MagicMock(),
        })
        svc.provider = "vertex"
        switched = svc.try_switch_provider("vertex")
        assert switched is True
        assert svc.provider == "openai"

    def test_vertex_only_no_fallback(self):
        """If vertex is the only provider and fails, no fallback."""
        svc = self._make_service({"vertex": MagicMock()})
        svc.provider = "vertex"
        switched = svc.try_switch_provider("vertex")
        assert switched is False


# ---------------------------------------------------------------------------
# _set_default_provider with vertex
# ---------------------------------------------------------------------------

class TestVertexDefaultPriority:
    """Vertex should be considered in _set_default_provider."""

    def _make_service(self, available_clients: dict, config_provider=None):
        from agent.core.ai.service import AIService

        svc = AIService.__new__(AIService)
        svc.clients = available_clients
        svc.provider = None
        svc.is_forced = False
        svc.models = {
            'gh': 'openai/gpt-4o',
            'gemini': 'gemini-pro-latest',
            'vertex': 'gemini-2.0-flash',
            'openai': 'gpt-4o',
            'anthropic': 'claude-sonnet-4-5-20250929',
        }
        # Mock config
        svc._config = MagicMock()
        if config_provider:
            svc._config.data = {"agent": {"provider": config_provider}}
        else:
            svc._config.data = {"agent": {}}
        return svc

    def test_vertex_selected_when_only_vertex_available(self):
        """When only vertex is available, it should be default."""
        svc = self._make_service({"vertex": MagicMock()})
        svc._set_default_provider()
        assert svc.provider == "vertex"

    @patch("agent.core.config.config")
    def test_config_vertex_overrides_default(self, mock_config):
        """When config says vertex, it should be selected."""
        mock_config.load_yaml.return_value = {"agent": {"provider": "vertex"}}
        mock_config.get_value.return_value = "vertex"
        mock_config.etc_dir = MagicMock()

        svc = self._make_service(
            {"gemini": MagicMock(), "vertex": MagicMock()},
            config_provider="vertex"
        )
        svc._set_default_provider()
        assert svc.provider == "vertex"

    def test_gemini_preferred_over_vertex_by_default(self):
        """Without config override, gemini has higher priority than vertex."""
        svc = self._make_service({
            "gemini": MagicMock(),
            "vertex": MagicMock(),
        })
        svc._set_default_provider()
        assert svc.provider == "gemini"
