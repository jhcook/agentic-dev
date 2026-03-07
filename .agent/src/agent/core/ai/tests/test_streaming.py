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

"""Unit tests for core/ai/streaming.py (INFRA-100)."""

import asyncio
import pytest

from agent.core.ai.protocols import AIRateLimitError, AIConnectionError
from agent.core.ai.streaming import ai_retry, process_stream


# ---------------------------------------------------------------------------
# ai_retry decorator
# ---------------------------------------------------------------------------

def test_ai_retry_succeeds_on_first_attempt():
    """ai_retry passes through the return value when the wrapped function succeeds."""

    @ai_retry(max_retries=3)
    async def always_ok():
        """Always succeeds."""
        return "ok"

    result = asyncio.run(always_ok())
    assert result == "ok"


def test_ai_retry_retries_on_rate_limit_then_succeeds():
    """ai_retry retries after AIRateLimitError and returns on eventual success."""
    attempts = {"count": 0}

    @ai_retry(max_retries=3, base_delay=0.01)
    async def flaky():
        """Fails twice with rate limit, then succeeds."""
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise AIRateLimitError("rate limited")
        return "recovered"

    result = asyncio.run(flaky())
    assert result == "recovered"
    assert attempts["count"] == 3


def test_ai_retry_exhausts_retries_and_raises():
    """ai_retry raises AIRateLimitError after all retries are exhausted."""
    call_count = {"n": 0}

    @ai_retry(max_retries=2, base_delay=0.01)
    async def always_fails():
        """Always raises a rate limit error."""
        call_count["n"] += 1
        raise AIRateLimitError("always limited")

    with pytest.raises(AIRateLimitError):
        asyncio.run(always_fails())

    # max_retries=2 means 1 initial attempt + 2 retries = 3 total calls
    assert call_count["n"] == 3


def test_ai_retry_retries_on_connection_error():
    """ai_retry retries after AIConnectionError and returns on eventual success."""
    attempts = {"count": 0}

    @ai_retry(max_retries=3, base_delay=0.01)
    async def connection_blip():
        """Fails once with connection error, then succeeds."""
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise AIConnectionError("connection blip")
        return "connected"

    result = asyncio.run(connection_blip())
    assert result == "connected"
    assert attempts["count"] == 2


def test_ai_retry_does_not_catch_generic_exceptions():
    """ai_retry does not suppress non-provider exceptions."""

    @ai_retry(max_retries=3, base_delay=0.01)
    async def programming_error():
        """Raises a ValueError (not a provider error)."""
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        asyncio.run(programming_error())


# ---------------------------------------------------------------------------
# process_stream helper
# ---------------------------------------------------------------------------

def test_process_stream_assembles_chunks():
    """process_stream concatenates all yielded chunks into one string."""

    async def _gen():
        for chunk in ["hello", " ", "world"]:
            yield chunk

    result = asyncio.run(process_stream(_gen()))
    assert result == "hello world"


def test_process_stream_skips_empty_chunks():
    """process_stream ignores falsy (empty string) chunks."""

    async def _gen():
        for chunk in ["a", "", "b", "", "c"]:
            yield chunk

    result = asyncio.run(process_stream(_gen()))
    assert result == "abc"


def test_process_stream_calls_on_chunk_callback():
    """process_stream invokes the on_chunk callback for each non-empty chunk."""
    received = []

    async def _gen():
        for chunk in ["x", "y", "z"]:
            yield chunk

    asyncio.run(process_stream(_gen(), on_chunk=received.append))
    assert received == ["x", "y", "z"]


def test_process_stream_empty_generator():
    """process_stream returns an empty string for an empty generator."""

    async def _gen():
        return
        yield  # make it an async generator

    result = asyncio.run(process_stream(_gen()))
    assert result == ""
