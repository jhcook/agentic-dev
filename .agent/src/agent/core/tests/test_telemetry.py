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

"""Unit tests for PiiScrubbingSpanProcessor.

Verifies that PII-sensitive span attributes are automatically scrubbed
before export regardless of whether the calling code scrubbed manually.
"""

from unittest.mock import MagicMock

import pytest

from types import SimpleNamespace
from agent.core.telemetry import PiiScrubbingSpanProcessor


class TestPiiScrubbingSpanProcessor:
    """Tests for the PII scrubbing span processor."""

    def _make_span(self, attributes: dict) -> SimpleNamespace:
        """Create a lightweight span-like object with a real attributes dict."""
        return SimpleNamespace(_attributes=attributes, attributes=attributes)

    def test_scrubs_llm_prompt_attribute(self) -> None:
        """PII in llm.request.prompt must be redacted."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = self._make_span({
            "llm.request.prompt": "Contact me at user@example.com",
            "llm.request.model": "gemini-2.5-pro",
        })

        proc.on_end(span)

        next_proc.on_end.assert_called_once()
        assert "[REDACTED_EMAIL]" in span.attributes["llm.request.prompt"]
        assert span.attributes["llm.request.model"] == "gemini-2.5-pro"

    def test_scrubs_llm_completion_attribute(self) -> None:
        """PII in llm.response.completion must be redacted."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = self._make_span({
            "llm.response.completion": "Your key is sk-abcdefghijklmnopqrstuvwxyz1234",
        })

        proc.on_end(span)

        assert "[REDACTED_SECRET]" in span.attributes["llm.response.completion"]

    def test_scrubs_custom_key_containing_input(self) -> None:
        """Any attribute key containing 'input' should be scrubbed."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = self._make_span({
            "tool.input": "Send to admin@company.org please",
        })

        proc.on_end(span)

        assert "[REDACTED_EMAIL]" in span.attributes["tool.input"]

    def test_does_not_scrub_non_sensitive_attributes(self) -> None:
        """Non-sensitive attributes must pass through unchanged."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = self._make_span({
            "latency_ms": "42.5",
            "service.name": "agentic-service",
        })

        proc.on_end(span)

        assert span.attributes["latency_ms"] == "42.5"
        assert span.attributes["service.name"] == "agentic-service"

    def test_handles_empty_attributes(self) -> None:
        """Spans with no attributes must not raise errors."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = self._make_span({})

        proc.on_end(span)

        next_proc.on_end.assert_called_once_with(span)

    def test_handles_none_attributes(self) -> None:
        """Spans with None attributes must not raise errors."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = MagicMock()
        span.attributes = None

        proc.on_end(span)

        next_proc.on_end.assert_called_once_with(span)

    def test_forwards_on_start(self) -> None:
        """on_start must be forwarded to the next processor."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)
        span = MagicMock()

        proc.on_start(span)

        next_proc.on_start.assert_called_once_with(span, None)

    def test_shutdown_delegates(self) -> None:
        """shutdown must delegate to the wrapped processor."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)

        proc.shutdown()

        next_proc.shutdown.assert_called_once()

    def test_force_flush_delegates(self) -> None:
        """force_flush must delegate to the wrapped processor."""
        next_proc = MagicMock()
        proc = PiiScrubbingSpanProcessor(next_proc)

        result = proc.force_flush(5000)

        next_proc.force_flush.assert_called_once_with(5000)
