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

@patch("agent.core.check.system.config")
def test_validate_story_success(mock_config, mock_story):
    """Test valid story returns None (success)."""
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
    res = validate_story("INFRA-TEST-001")
    assert res is None

@patch("agent.core.check.system.config")
def test_validate_story_missing_sections(mock_config, mock_story):
    """Test invalid story raises Exit(1)."""
    # Invalid Content
    mock_story.write_text("## Problem Statement\nOnly one section.")
    
    # Mock config.stories_dir explicitly
    mock_stories_dir = MagicMock()
    mock_config.stories_dir = mock_stories_dir
    mock_stories_dir.rglob.return_value = [mock_story]
    
    # return_bool removed -> raises Typer Exit
    with pytest.raises(Exit) as exc:
        validate_story("INFRA-TEST-001")
    assert exc.value.exit_code == 1
