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
from unittest.mock import MagicMock, patch

def test_regression_infra_146_zero_syntax_advisories(capsys):
    """Regression: Verify that a runbook targeting 15 files with malformed blocks produces 0 advisories."""
    file_list = [f"backend/voice/tools/tool_{i}.py" for i in range(15)]

    # Mock results list to simulate malformed skips for all 15 files
    mock_results = [(f, "sr_replace_malformed_empty_search", None) for f in file_list]

    from agent.commands.runbook_gates import _display_sr_validation_summary
    _display_sr_validation_summary(mock_results)

    captured = capsys.readouterr()
    output = captured.out
    assert "15 malformed block(s)" in output
    assert "stripped to prevent false AST corruption" in output
    assert "0 file(s) failed syntax validation" in output
