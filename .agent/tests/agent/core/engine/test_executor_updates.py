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
from agent.core.engine.executor import TaskExecutor
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_executor_imports_tool_registry():
    """Verify AC-4: TaskExecutor module imports ToolRegistry (INFRA-145)."""
    # executor.py now imports ToolRegistry as part of unified tool access
    from agent.core.engine import executor as ex_module
    assert hasattr(ex_module, "ToolRegistry"), (
        "executor must import ToolRegistry for unified tool access (INFRA-145 AC-4)"
    )


def test_task_executor_is_class():
    """Verify TaskExecutor is a concrete class with expected interface."""
    assert callable(TaskExecutor)
    assert "run_parallel" in dir(TaskExecutor)
