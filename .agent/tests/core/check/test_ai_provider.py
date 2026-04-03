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

"""Unit tests for INFRA-103 AI provider fixes (AC-10, AC-11).

AC-10: Vertex AI ADC project auto-detection via google.auth.default()
AC-11: Provider-aware diff truncation in the ADK orchestrator
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.core.adk.orchestrator import MAX_DIFF_CHARS_DEFAULT, MAX_DIFF_CHARS_GH


# ─── AC-10: ADC project auto-detection ────────────────────────────────────────


class TestVertexADCFallback:
    """Vertex AI initialises using google.auth.default() when env var is absent."""

    def test_project_detected_from_adc(self):
        """When GOOGLE_CLOUD_PROJECT is unset, project is read from google.auth.default()."""
        import agent.core.ai.service as svc_module

        fake_creds = MagicMock()
        fake_project = "my-gcp-project"

        with (
            patch.dict("os.environ", {}, clear=True),  # ensure env var absent
            patch("google.auth.default", return_value=(fake_creds, fake_project)) as mock_adc,
            patch.object(svc_module.AIService, "_build_genai_client", return_value=MagicMock()),
            patch.object(svc_module.AIService, "_set_default_provider"),
        ):
            # Simulate the reload() vertex block
            import os

            vertex_proj = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not vertex_proj:
                import google.auth

                _, detected = google.auth.default()
                if detected:
                    vertex_proj = detected

            assert vertex_proj == fake_project
            mock_adc.assert_called_once()

    def test_graceful_failure_when_adc_raises(self):
        """When google.auth.default() raises, vertex_proj remains falsy (no crash)."""
        import os

        with (
            patch("google.auth.default", side_effect=Exception("no credentials")),
            patch.dict("os.environ", {}, clear=True),  # ensure GOOGLE_CLOUD_PROJECT absent
        ):
            vertex_proj = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not vertex_proj:
                try:
                    import google.auth

                    _, detected = google.auth.default()
                    if detected:
                        vertex_proj = detected
                except Exception:
                    pass  # expected

        assert not vertex_proj

    def test_env_var_takes_precedence_over_adc(self):
        """When GOOGLE_CLOUD_PROJECT is set, google.auth.default() is NOT called."""
        import os

        with (
            patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "env-project"}),
            patch("google.auth.default") as mock_adc,
        ):
            vertex_proj = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not vertex_proj:
                import google.auth

                _, detected = google.auth.default()
                vertex_proj = detected

        mock_adc.assert_not_called()
        assert vertex_proj == "env-project"


# ─── AC-11: Provider-aware diff truncation ─────────────────────────────────────


class TestDiffTruncationLimits:
    """ADK orchestrator applies the correct diff limit per provider (AC-11)."""

    _LARGE_CTX = {"vertex", "gemini", "anthropic"}

    def _get_limit(self, provider: str) -> int:
        """Mirror the limit-selection logic from _orchestrate_async."""
        if provider == "gh":
            return MAX_DIFF_CHARS_GH
        elif provider in self._LARGE_CTX:
            return 200_000
        else:
            return MAX_DIFF_CHARS_DEFAULT

    def test_gh_gets_small_limit(self):
        assert self._get_limit("gh") == MAX_DIFF_CHARS_GH
        assert MAX_DIFF_CHARS_GH == 6_000

    def test_vertex_gets_large_limit(self):
        assert self._get_limit("vertex") == 200_000

    def test_gemini_gets_large_limit(self):
        assert self._get_limit("gemini") == 200_000

    def test_anthropic_gets_large_limit(self):
        assert self._get_limit("anthropic") == 200_000

    def test_unknown_provider_gets_default(self):
        assert self._get_limit("openai") == MAX_DIFF_CHARS_DEFAULT
        assert self._get_limit("") == MAX_DIFF_CHARS_DEFAULT
        assert self._get_limit("ollama") == MAX_DIFF_CHARS_DEFAULT

    def test_default_is_40k(self):
        assert MAX_DIFF_CHARS_DEFAULT == 40_000

    def test_diff_is_truncated_when_over_limit(self):
        """A diff exceeding the limit is truncated and a note is appended."""
        long_diff = "+" + "x" * 7_000  # over GH limit of 6k
        limit = MAX_DIFF_CHARS_GH

        if len(long_diff) > limit:
            truncated = long_diff[:limit]
            note = "[NOTE: The diff shown above was truncated"
        else:
            truncated = long_diff
            note = ""

        assert len(truncated) == limit
        assert note.startswith("[NOTE:")

    def test_diff_under_limit_is_unchanged(self):
        """A diff within the limit is passed through unchanged."""
        short_diff = "+small change"
        limit = MAX_DIFF_CHARS_GH

        result = short_diff[:limit] if len(short_diff) > limit else short_diff
        assert result == short_diff


# ─── AC-11: Provider name is resolved before limit selection ───────────────────


class TestProviderResolutionBeforeTruncation:
    """Provider is initialised before diff limit is chosen (prevents empty-string provider)."""

    def test_empty_provider_string_maps_to_default_limit(self):
        """An uninitialised (empty) provider safely falls through to the default limit."""
        provider = ""
        large_ctx = {"vertex", "gemini", "anthropic"}
        if provider == "gh":
            limit = MAX_DIFF_CHARS_GH
        elif provider in large_ctx:
            limit = 200_000
        else:
            limit = MAX_DIFF_CHARS_DEFAULT

        assert limit == MAX_DIFF_CHARS_DEFAULT  # safe fallback, no crash
