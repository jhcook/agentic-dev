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

"""test_telemetry_infra_167 module."""

import pytest
from io import StringIO
from rich.console import Console
from observability.token_counter import UsageTracker, get_token_count
from observability.telemetry import record_token_usage
from unittest.mock import patch

def test_token_counter_heuristic_fallback():
    """Verify the 4-char heuristic fallback when tiktoken is unavailable."""
    with patch("tiktoken.encoding_for_model", side_effect=ImportError):
        text = "Hello World" # 11 chars
        count = get_token_count(text)
        assert count == 11 // 4 # Should be 2

def test_usage_tracker_summary_rendering():
    """Ensure UsageTracker outputs a readable table to the console."""
    tracker = UsageTracker()
    tracker.record_call("gpt-4", input_tokens=150, output_tokens=300)
    tracker.record_call("gpt-3.5-turbo", input_tokens=50, output_tokens=100)

    # Capture output
    buf = StringIO()
    tracker.console = Console(file=buf, force_terminal=False)
    tracker.print_summary()
    output = buf.getvalue()

    assert "LLM Token Consumption Summary" in output
    assert "gpt-4" in output
    assert "450" in output # Total for gpt-4
    assert "600" in output # Grand total (450 + 150)

@patch("observability.telemetry.token_counter")
def test_otel_metric_recording(mock_counter):
    """Verify that metrics are sent to the OTel meter provider."""
    record_token_usage("gpt-4", 10, 20)
    
    # Should be called once for input, once for output
    assert mock_counter.add.call_count == 2
    mock_counter.add.assert_any_call(10, {"model": "gpt-4", "type": "input"})
    mock_counter.add.assert_any_call(20, {"model": "gpt-4", "type": "output"})
