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
from pathlib import Path
from agent.core import utils
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_fs(tmp_path):
    # Setup temporary directories mimicking structure
    stories = tmp_path / ".agent" / "stories"
    stories.mkdir(parents=True)
    rules = tmp_path / ".agent" / "rules"
    rules.mkdir(parents=True)
    runbooks = tmp_path / ".agent" / "runbooks"
    runbooks.mkdir(parents=True)
    
    return {"root": tmp_path, "stories": stories, "rules": rules, "runbooks": runbooks}


def test_sanitize_title():
    assert utils.sanitize_title("Hello World 123") == "hello-world-123"
    assert utils.sanitize_title("Complex... Title!!!") == "complex-title"
    assert utils.sanitize_title("  Spaces  ") == "spaces"

def test_find_story_file(mock_fs):
    story_file = mock_fs["stories"] / "STORY-123-test-story.md"
    story_file.touch()
    
    with patch("agent.core.config.config.stories_dir", mock_fs["stories"]):
        # Exact match start
        found = utils.find_story_file("STORY-123")
        assert found == story_file
        
        # Non-existent
        assert utils.find_story_file("STORY-999") is None
        
        # Partial ID should technically match if it starts with it
        assert utils.find_story_file("STORY") == story_file

def test_find_runbook_file(mock_fs):
    runbook_file = mock_fs["runbooks"] / "RUN-456-deployment.md"
    runbook_file.touch()
    
    with patch("agent.core.config.config.runbooks_dir", mock_fs["runbooks"]):
        found = utils.find_runbook_file("RUN-456")
        assert found == runbook_file
        assert utils.find_runbook_file("RUN-000") is None

def test_load_governance_context(mock_fs):
    rule1 = mock_fs["rules"] / "rule1.mdc"
    rule1.write_text("Rule 1 Content")
    
    rule2 = mock_fs["rules"] / "rule2.mdc"
    rule2.write_text("Rule 2 Content")
    
    with patch("agent.core.config.config.rules_dir", mock_fs["rules"]):
        context = utils.load_governance_context()
        
        assert "GOVERNANCE RULES:" in context
        assert "--- RULE: rule1.mdc ---" in context
        assert "Rule 1 Content" in context
        assert "--- RULE: rule2.mdc ---" in context
        assert "Rule 2 Content" in context

def test_load_governance_context_empty(mock_fs):
    # Empty rules dir
    with patch("agent.core.config.config.rules_dir", mock_fs["rules"]):
        context = utils.load_governance_context()
        assert "(No rules found)" in context # Assuming implementation does this or similar
