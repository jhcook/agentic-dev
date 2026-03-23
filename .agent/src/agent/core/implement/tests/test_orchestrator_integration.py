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

"""Integration tests for Orchestrator with concurrent retries (INFRA-169)."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from agent.core.implement.orchestrator import Orchestrator
from agent.core.implement.retry import MaxRetriesExceededError

@pytest.mark.asyncio
async def test_orchestrator_parallel_chunk_success():
    """Verify multiple chunks are processed in parallel within a phase."""
    orchestrator = Orchestrator(story_id="INFRA-169", yes=True)
    
    # Mock the internal async applier (added in Step 2)
    with patch("agent.core.implement.guards.apply_change_to_file", new_callable=AsyncMock) as mock_apply:
        mock_apply.return_value = True
        
        chunk_content = "#### [NEW] file1.py\n```python\nprint(1)\n```\n#### [NEW] file2.py\n```python\nprint(2)\n```"