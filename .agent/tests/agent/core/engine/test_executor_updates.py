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
from agent.core.engine.executor import execute
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_executor_yields_thinking_status():
    """Verify AC-4: Executor yields 'Thinking...' before results."""
    mock_tool = MagicMock()
    mock_tool.arun = AsyncMock(return_value="Final Result")
    
    with patch("agent.core.engine.executor._get_tool", return_value=mock_tool):
        generator = execute("some_tool", {})
        
        # First yield should be the status update
        status = await generator.__anext__()
        assert status == "Thinking..."
        
        # Second yield should be the result
        result = await generator.__anext__()
        assert result == "Final Result"
