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

"""test_decomposition_integrity module."""

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
from unittest.mock import patch, MagicMock

"""Regression tests for the decomposed governance package facade."""

def test_facade_imports():
    """Ensure re-exported symbols in __init__.py are resolvable."""
    try:
        from agent.core.governance import (
            load_roles,
            convene_council_full,
            log_governance_event
        )
    except ImportError as e:
        pytest.fail(f"Decomposition broke package facade: {e}")

@patch("agent.core.governance.panel.ai_service.complete")
def test_convene_council_orchestration(mock_complete):
    """Verify the native panel loop correctly orchestrates decomposed helpers."""
    from agent.core.governance.panel import convene_council_full
    
    # Mock AI response with structured format
    mock_complete.return_value = "VERDICT: PASS\nSUMMARY: OK\nFINDINGS:\n- Valid finding (Source: test.py)"
    
    result = convene_council_full(
        story_id="TEST-1",
        story_content="...",
        rules_content="...",
        instructions_content="...",
        full_diff="+++ b/test.py\n@@ -1,1 +1,1 @@\n+print('hi')",
        thorough=True
    )
    
    assert result["verdict"] == "PASS"
    assert "roles" in result["json_report"]
    assert len(result["json_report"]["roles"]) > 0
