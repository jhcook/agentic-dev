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
"""Unit tests for GHProvider (INFRA-108).

Covers generate(), stream(), and subprocess exit-code / stderr error mapping.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from agent.core.ai.protocols import AIConfigurationError, AIRateLimitError
from agent.core.ai.providers.gh import GHProvider


def _make_provider(model_name: str = "openai/gpt-4o") -> GHProvider:
    """Return a GHProvider with the given model name."""
    return GHProvider(client=None, model_name=model_name)


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock CompletedProcess object."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# generate() — success
# ---------------------------------------------------------------------------

def test_generate_returns_stdout_on_success():
    """generate() returns stripped stdout when gh exits with code 0."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=0, stdout="  Great answer!  ")
        result = asyncio.run(provider.generate("hello"))

    assert result == "Great answer!"


def test_generate_passes_combined_prompt_as_stdin():
    """generate() sends system_prompt + user prompt as combined stdin input."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=0, stdout="ok")
        asyncio.run(provider.generate("Tell me a joke", system_prompt="Be funny"))

        call_kwargs = mock_run.call_args[1]
        assert "Be funny" in call_kwargs["input"]
        assert "Tell me a joke" in call_kwargs["input"]


# ---------------------------------------------------------------------------
# generate() — error mapping
# ---------------------------------------------------------------------------

def test_generate_raises_rate_limit_on_rate_limit_stderr():
    """generate() raises AIRateLimitError when stderr contains 'rate limit'."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=1, stderr="rate limit exceeded")

        with pytest.raises(AIRateLimitError):
            asyncio.run(provider.generate("hello"))


def test_generate_raises_rate_limit_on_too_many_requests():
    """generate() raises AIRateLimitError for 'too many requests' in stderr."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=1, stderr="too many requests")

        with pytest.raises(AIRateLimitError):
            asyncio.run(provider.generate("hello"))


def test_generate_raises_configuration_error_on_too_large():
    """generate() raises AIConfigurationError when context is too large."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=1, stderr="request too large for model")

        with pytest.raises(AIConfigurationError, match="context limit"):
            asyncio.run(provider.generate("hello"))


def test_generate_raises_configuration_error_on_413():
    """generate() raises AIConfigurationError on 413 errors."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=1, stderr="413 Payload Too Large")

        with pytest.raises(AIConfigurationError):
            asyncio.run(provider.generate("hello"))


def test_generate_raises_runtime_error_on_generic_failure():
    """generate() raises RuntimeError for unrecognised non-zero exit codes."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=1, stderr="some unknown error")

        with pytest.raises(RuntimeError):
            asyncio.run(provider.generate("hello"))


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

def test_stream_yields_generate_result_as_single_chunk():
    """stream() yields the full generate() response as one chunk."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=0, stdout="streaming response")

        async def _collect() -> list:
            """Collect all streamed chunks."""
            return [c async for c in provider.stream("hello")]

        chunks = asyncio.run(_collect())

    assert chunks == ["streaming response"]


def test_stream_yields_nothing_on_empty_response():
    """stream() yields nothing when generate() returns an empty string."""
    provider = _make_provider()

    with patch("agent.core.ai.providers.gh.subprocess.run") as mock_run:
        mock_run.return_value = _make_proc(returncode=0, stdout="   ")

        async def _collect() -> list:
            """Collect all streamed chunks."""
            return [c async for c in provider.stream("hello")]

        chunks = asyncio.run(_collect())

    assert chunks == []


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_supports_tools_returns_false():
    """GHProvider.supports_tools returns False."""
    provider = _make_provider()
    assert provider.supports_tools() is False


def test_get_models_contains_model_name():
    """get_models returns a list containing the configured model name."""
    provider = _make_provider("openai/gpt-4o-mini")
    assert "openai/gpt-4o-mini" in provider.get_models()
