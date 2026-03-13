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
Unit tests for tracing module.
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.core.ai.tracing import llm_span, mark_as_hallucination

def test_llm_span():
    """Ensure llm_span context manager traces properly."""
    with patch("agent.core.ai.tracing.get_tracer") as mock_tracer:
        mock_span = MagicMock()
        mock_tracer.return_value.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        with llm_span("test_name", "test_model", "test_prompt") as span:
            assert span == mock_span

        mock_span.set_attribute.assert_any_call("llm.request.model", "test_model")

def test_mark_as_hallucination():
    """Ensure mark_as_hallucination sets score."""
    mock_span = MagicMock()
    mark_as_hallucination(span=mock_span)
    mock_span.set_attribute.assert_any_call("score", 0)
    mock_span.set_attribute.assert_any_call("llm.failure_type", "hallucination")
