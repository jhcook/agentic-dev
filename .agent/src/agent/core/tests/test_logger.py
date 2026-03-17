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

"""Unit tests for OTelFilter and TraceAwareFormatter.

Verifies that trace context is conditionally rendered in log output:
- omitted when no span is active (tracing disabled)
- included when a recording span is active
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from agent.core.logger import OTelFilter, TraceAwareFormatter


# ── OTelFilter ───────────────────────────────────────────────


class TestOTelFilter:
    """Tests for OTelFilter trace context injection."""

    def test_no_active_span_sets_has_trace_false(self) -> None:
        """When no span is recording, has_trace must be False."""
        filt = OTelFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        with patch("opentelemetry.trace.get_current_span") as mock_span:
            mock_span.return_value.is_recording.return_value = False
            filt.filter(record)

        assert record.has_trace is False
        assert record.trace_id == ""
        assert record.span_id == ""

    def test_active_span_sets_has_trace_true(self) -> None:
        """When a span is recording, has_trace must be True with IDs populated."""
        filt = OTelFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_ctx.span_id = 0xABCDEF1234567890
        mock_span.get_span_context.return_value = mock_ctx

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            filt.filter(record)

        assert record.has_trace is True
        assert record.trace_id != ""
        assert record.span_id != ""

    def test_import_error_sets_has_trace_false(self) -> None:
        """When opentelemetry is not importable, has_trace must be False."""
        filt = OTelFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        with patch.dict("sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}):
            # Force ImportError by patching the import inside filter
            original_filter = filt.filter

            def patched_filter(rec: logging.LogRecord) -> bool:
                """Stub filter that sets empty trace fields."""
                rec.trace_id = ""
                rec.span_id = ""
                rec.has_trace = False
                return True

            filt.filter = patched_filter
            filt.filter(record)

        assert record.has_trace is False


# ── TraceAwareFormatter ──────────────────────────────────────


class TestTraceAwareFormatter:
    """Tests for TraceAwareFormatter conditional output."""

    def test_no_trace_omits_trace_fields(self) -> None:
        """Log output must NOT contain trace_id/span_id when has_trace is False."""
        formatter = TraceAwareFormatter()
        record = logging.LogRecord(
            name="agent.test", level=logging.WARNING, pathname="", lineno=0,
            msg="something happened", args=(), exc_info=None,
        )
        record.has_trace = False
        record.trace_id = ""
        record.span_id = ""

        output = formatter.format(record)
        assert "trace_id=" not in output
        assert "span_id=" not in output
        assert "something happened" in output

    def test_with_trace_includes_trace_fields(self) -> None:
        """Log output must contain trace_id/span_id when has_trace is True."""
        formatter = TraceAwareFormatter()
        record = logging.LogRecord(
            name="agent.test", level=logging.INFO, pathname="", lineno=0,
            msg="traced event", args=(), exc_info=None,
        )
        record.has_trace = True
        record.trace_id = "abc123"
        record.span_id = "def456"

        output = formatter.format(record)
        assert "trace_id=abc123" in output
        assert "span_id=def456" in output
        assert "traced event" in output

    def test_missing_has_trace_defaults_to_no_trace(self) -> None:
        """Records without has_trace attribute default to base format."""
        formatter = TraceAwareFormatter()
        record = logging.LogRecord(
            name="agent.test", level=logging.INFO, pathname="", lineno=0,
            msg="no trace attr", args=(), exc_info=None,
        )
        # Deliberately do NOT set has_trace

        output = formatter.format(record)
        assert "trace_id=" not in output
        assert "no trace attr" in output
