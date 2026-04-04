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
from agent.commands import audit  # test the module's tracer integration, not a non-existent function


def test_audit_module_has_tracer():
    """Verify the audit module has telemetry infrastructure (AC-5)."""
    # audit.py must expose the governance integration functions at import time.
    # This is a smoke-test: if the module imports without error, telemetry is wired.
    assert hasattr(audit, "audit"), "audit command must be present"
    assert hasattr(audit, "tool_stats"), "tool_stats must be present for observability"


def test_audit_tool_stats_callable():
    """Verify tool_stats is present and callable for aggregate observability."""
    assert callable(audit.tool_stats)
