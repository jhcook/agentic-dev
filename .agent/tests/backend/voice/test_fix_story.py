import pytest
from unittest.mock import MagicMock, patch, mock_open
from backend.voice.tools.fix_story import validate_and_fix_story

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

@pytest.fixture
def mock_deps():
    with patch('backend.voice.tools.fix_story.subprocess.run') as mock_run, \
         patch('backend.voice.tools.fix_story.EventBus') as mock_bus, \
         patch('backend.voice.tools.fix_story.agent_config') as mock_config, \
         patch('backend.voice.tools.fix_story.ai_service') as mock_ai:
        yield mock_run, mock_bus, mock_config, mock_ai

def test_validation_passes_initially(mock_deps):
    mock_run, mock_bus, _, _ = mock_deps
    
    # Validation succeeds
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Success"
    
    result = validate_and_fix_story.func("WEB-001", config={"configurable": {"thread_id": "s1"}})
    
    assert "is valid" in result
    mock_bus.publish.assert_called() # Check it logs start
    mock_run.assert_called_once()

def test_validation_fails_and_fixes(mock_deps):
    mock_run, mock_bus, mock_config, mock_ai = mock_deps
    
    # 1. Validation fails
    fail_result = MagicMock()
    fail_result.returncode = 1
    fail_result.stdout = "Missing sections: Problem Statement"
    fail_result.stderr = ""
    
    # 2. Retry succeeds
    pass_result = MagicMock()
    pass_result.returncode = 0
    pass_result.stdout = "Success"
    
    mock_run.side_effect = [fail_result, pass_result]
    
    # Mock finding file
    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    mock_path.read_text.return_value = "# Header"
    
    mock_config.stories_dir.rglob.return_value = [mock_path]
    
    # Mock AI
    mock_ai.complete.return_value = "## Problem Statement\nFix details."
    
    # Run
    result = validate_and_fix_story.func("WEB-001", config={"configurable": {"thread_id": "s1"}})
    
    # Verification
    assert "Validation now passes" in result
    
    # Check AI called
    mock_ai.complete.assert_called_once()
    
    # Check file written
    mock_path.write_text.assert_called_once()
    content_written = mock_path.write_text.call_args[0][0]
    assert "## Problem Statement" in content_written

def test_validation_fails_no_pattern(mock_deps):
    mock_run, _, _, _ = mock_deps
    
    # Validation fails but output doesn't match regex
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = "Random error"
    mock_run.return_value.stderr = ""
    
    result = validate_and_fix_story.func("WEB-001")
    
    assert "could not identify missing sections" in result
