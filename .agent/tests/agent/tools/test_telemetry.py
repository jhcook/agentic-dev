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
import time
from agent.tools.telemetry import track_tool_usage, get_tool_metrics

@track_tool_usage("test")
def mock_tool(should_succeed=True):
    if not should_succeed:
        return "Error: Not found"
    return [1, 2, 3]

def test_track_tool_usage_metrics():
    # Trigger calls
    mock_tool(should_succeed=True)
    mock_tool(should_succeed=False)
    
    metrics = get_tool_metrics("test.mock_tool")
    entries = metrics["test.mock_tool"]
    
    assert len(entries) == 2
    assert entries[0]["hit"] is True
    assert entries[0]["result_count"] == 3
    assert entries[1]["hit"] is False
    assert entries[0]["latency_ms"] > 0
