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
Unit tests for the telemetry instrumentation logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.core.telemetry import trace_llm_call, ATTR_LLM_PROMPT, ATTR_LATENCY_MS

@pytest.mark.asyncio
async def test_trace_llm_call_scrubs_pii():
    """
    Ensure that the trace_llm_call decorator scrubs PII from attributes.
    """
    # Mocking scrub_sensitive_data to verify it's called
    with patch("agent.core.telemetry.scrub_sensitive_data") as mock_scrub:
        mock_scrub.return_value = "REDACTED"
        
        @trace_llm_call(model_name="gpt-4o")
        async def mock_llm(prompt: str):
            """Mock llm call."""
            return "Result"

        # Mock trace span
        with patch("agent.core.telemetry.get_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.return_value.start_as_current_span.return_value.__enter__.return_value = mock_span
            
            await mock_llm(prompt="My email is [REDACTED:EMAIL]")
            
            # Verify scrub was called
            mock_scrub.assert_called()
            # Verify span attribute was set to redacted value
            mock_span.set_attribute.assert_any_call(ATTR_LLM_PROMPT, "REDACTED")

@pytest.mark.asyncio
async def test_trace_llm_call_records_latency():
    """
    Ensure that latency_ms is recorded as a float.
    """
    @trace_llm_call(model_name="gpt-4o")
    async def mock_llm(prompt: str):
        """Mock llm call."""
        return "Result"

    with patch("agent.core.telemetry.get_tracer") as mock_tracer:
        mock_span = MagicMock()
        mock_tracer.return_value.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        await mock_llm(prompt="hello")
        
        # Check if set_attribute was called with latency_ms
        calls = [call.args for call in mock_span.set_attribute.call_args_list]
        latency_call = [c for c in calls if c[0] == ATTR_LATENCY_MS]
        assert len(latency_call) == 1
        assert isinstance(latency_call[0][1], float)