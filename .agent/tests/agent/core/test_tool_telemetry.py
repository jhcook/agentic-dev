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

import pytest
import json
from unittest.mock import MagicMock, patch
from agent.commands.audit import tool_execution_span

def test_tool_span_integration():
    """Verify that tool_execution_span correctly creates spans with metadata."""
    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        tool_inputs = {"query": "test"}
        with tool_execution_span("search", "voice", tool_inputs):
            pass
            
        mock_tracer.start_as_current_span.assert_called_once()
        args, kwargs = mock_tracer.start_as_current_span.call_args
        assert "tool_execute:search" in args[0]
        assert kwargs["attributes"]["tool.interface"] == "voice"
        assert "query" in kwargs["attributes"]["tool.input_keys"]
