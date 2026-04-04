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
from agent.commands.runbook_gates import validate_runbook_syntax_for_story
from unittest.mock import MagicMock, patch

def test_regression_infra_146_zero_syntax_advisories():
    """Regression: Verify that a runbook targeting 15 files with malformed blocks produces 0 advisories."""
    # We mock the parser to return 'malformed' events for multiple tool files
    # to ensure the gates.py logic summarizes them correctly per AC-5.
    file_list = [f"backend/voice/tools/tool_{i}.py" for i in range(15)]
    
    # Mock the parser to yield nothing for these files (simulating empty search detection)
    with patch("agent.commands.runbook_gates.parse_sr_blocks", return_value=[]):
        # Mock results list to simulate malformed skips for all 15 files
        mock_results = [(f, "sr_replace_malformed_empty_search", None) for f in file_list]
        
        with patch("agent.commands.runbook_gates.Console") as mock_console_class:
            mock_console = mock_console_class.return_value
            
            # We use a custom runner that injects these results into the gate summary logic
            # or directly test the summary logic in runbook_gates.py
            from agent.commands.runbook_gates import _display_sr_validation_summary
            
            _display_sr_validation_summary(mock_results)
            
            # Assert that the summary output contains the expected warning about skipped blocks
            # and NOT the 'failed syntax validation' error message.
            printed_text = "".join(call.args[0] for call in mock_console.print.call_args_list if call.args)
            assert "15 malformed block(s)" in printed_text
            assert "skipped to prevent false AST corruption" in printed_text
            assert "0 file(s) failed syntax validation" in printed_text
