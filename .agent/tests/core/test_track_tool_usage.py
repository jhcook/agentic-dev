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

"""Tests for the track_tool_usage context manager (AC-7 / ADR-046).

Uses a collecting SpanExporter to capture and assert on emitted OTel spans,
verifying that required attributes (tool.name, tool.duration_ms, tool.success,
session_id) are present on every tool invocation.
"""

import pytest
from unittest.mock import patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from agent.core.adk.tool_security import track_tool_usage


class _CollectingExporter(SpanExporter):
    """Lightweight in-memory exporter that collects finished spans for assertions."""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=None):
        return True

    def clear(self):
        self.spans.clear()


# Module-level setup: create a single TracerProvider for all tests in this module.
_exporter = _CollectingExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))


@pytest.fixture(autouse=True)
def _patch_tracer():
    """Patch the tracer used by tool_security to use our collecting provider."""
    test_tracer = _provider.get_tracer(__name__)
    _exporter.clear()
    with patch("agent.core.adk.tool_security.tracer", test_tracer):
        yield


class TestTrackToolUsageSpan:
    """Verify OTel spans emitted by track_tool_usage."""

    def test_success_span_attributes(self):
        """On a successful tool call, required attributes are emitted."""
        with track_tool_usage("my_tool", session_id="sess-123") as span:
            span.set_attribute("tool.args", '{"key": "val"}')

        assert len(_exporter.spans) == 1

        s = _exporter.spans[0]
        attrs = dict(s.attributes)
        assert attrs["tool.name"] == "my_tool"
        assert attrs["session_id"] == "sess-123"
        assert attrs["tool.success"] is True
        assert "tool.duration_ms" in attrs
        assert attrs["tool.duration_ms"] >= 0

    def test_failure_span_attributes(self):
        """On a failed tool call, tool.success is False and exception is recorded."""
        with pytest.raises(ValueError, match="boom"):
            with track_tool_usage("fail_tool", session_id="sess-456"):
                raise ValueError("boom")

        assert len(_exporter.spans) == 1

        s = _exporter.spans[0]
        attrs = dict(s.attributes)
        assert attrs["tool.name"] == "fail_tool"
        assert attrs["session_id"] == "sess-456"
        assert attrs["tool.success"] is False
        assert attrs["tool.duration_ms"] >= 0
        # Exception should be recorded as an event
        assert any(e.name == "exception" for e in s.events)

    def test_default_session_id_empty(self):
        """When session_id is omitted, it defaults to empty string."""
        with track_tool_usage("bare_tool"):
            pass

        assert len(_exporter.spans) == 1
        assert dict(_exporter.spans[0].attributes)["session_id"] == ""

    def test_dispatch_tool_creates_span(self):
        """AgentSession._dispatch_tool creates a span with session_id via track_tool_usage."""
        from unittest.mock import MagicMock

        from agent.core.session import AgentSession

        mock_provider = MagicMock()
        session = AgentSession(
            provider=mock_provider,
            system_prompt="test",
            tools=[],
            tool_handlers={"echo": lambda msg="": msg},
            session_id="dispatch-789",
        )

        result = session._dispatch_tool("echo", {"msg": "hello"})
        assert result == "hello"

        assert len(_exporter.spans) == 1
        attrs = dict(_exporter.spans[0].attributes)
        assert attrs["tool.name"] == "echo"
        assert attrs["session_id"] == "dispatch-789"
        assert attrs["tool.success"] is True
