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
from typer import Exit
from agent.commands.check import validate_story

@pytest.fixture
def mock_story(tmp_path):
    story_dir = tmp_path / ".agent" / "cache" / "stories" / "INFRA"
    story_dir.mkdir(parents=True)
    story_file = story_dir / "INFRA-TEST-001-test-story.md"
    return story_file

@patch("agent.commands.check.config")
def test_validate_story_success(mock_config, mock_story):
    """Test valid story returns True."""
    # Setup Valid Content
    content = """
## Problem Statement
X
## User Story
Y
## Acceptance Criteria
Z
## Non-Functional Requirements
A
## Impact Analysis Summary
B
## Test Strategy
C
## Rollback Plan
D
"""
    mock_story.write_text(content)
    
    # Mock config.stories_dir explicitly as a MagicMock
    mock_stories_dir = MagicMock()
    mock_config.stories_dir = mock_stories_dir
    mock_stories_dir.rglob.return_value = [mock_story]
    
    # Call
    res = validate_story("INFRA-TEST-001", return_bool=True)
    assert res is True

@patch("agent.commands.check.config")
def test_validate_story_missing_sections(mock_config, mock_story):
    """Test invalid story raises Exit(1) or returns False."""
    # Invalid Content
    mock_story.write_text("## Problem Statement\nOnly one section.")
    
    # Mock config.stories_dir explicitly
    mock_stories_dir = MagicMock()
    mock_config.stories_dir = mock_stories_dir
    mock_stories_dir.rglob.return_value = [mock_story]
    
    # return_bool = True -> returns False
    res = validate_story("INFRA-TEST-001", return_bool=True)
    assert res is False
    
    # return_bool = False -> raises Typer Exit
    with pytest.raises(Exit):
        validate_story("INFRA-TEST-001")

@patch("agent.commands.check.config")
@patch("agent.commands.check.InteractiveFixer")
@patch("agent.commands.check.Confirm")
@patch("agent.commands.check.Prompt")
def test_validate_story_interactive_trigger(mock_prompt, mock_confirm, mock_fixer_cls, mock_config, mock_story):
    """Test that interactive mode triggers the Fixer."""
    mock_story.write_text("Invalid content")
    
    mock_stories_dir = MagicMock()
    mock_config.stories_dir = mock_stories_dir
    mock_stories_dir.rglob.return_value = [mock_story]
    
    # Setup Fixer Mock
    fixer_instance = mock_fixer_cls.return_value
    fixer_instance.analyze_failure.return_value = [
        {"title": "Fix 1", "description": "Desc", "patched_content": "Fixed"}
    ]
    fixer_instance.apply_fix.return_value = True
    fixer_instance.verify_fix.return_value = True
    
    # Mock UI Interactions
    mock_prompt.ask.return_value = "1" # Select Option 1
    mock_confirm.ask.return_value = True # Confirm Apply
    
    # Run interactive
    # Should raise Exit(1) or 0 depending on success flow?
    # Logic: if verify_fix returns True, it returns True (if return_bool defaults to False, logic says check returns True)
    # The existing code: 
    # if fixer.verify_fix(check):
    #    return True
    
    res = validate_story("INFRA-TEST-001", interactive=True)
    assert res is True
    
    # Verify Fixer was called
    fixer_instance.analyze_failure.assert_called()
    fixer_instance.apply_fix.assert_called()
    fixer_instance.verify_fix.assert_called()
