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
from unittest.mock import patch
from agent.core.fixer import InteractiveFixer


@pytest.fixture
def fixer():
    return InteractiveFixer()

def test_analyze_failure_extracts_clean_json(fixer, tmp_path, monkeypatch):
    """Test extracting clean JSON list."""
    monkeypatch.chdir(tmp_path)
    # Create dummy file
    d = tmp_path / "subdir"
    d.mkdir()
    p = d / "test.md"
    p.write_text("content")
    file_path = str(p)

    mock_response = '[{"title": "Fix 1", "description": "Desc 1", "patched_content": "fixed"}]'
    
    with patch.object(fixer.ai, 'get_completion', return_value=mock_response):
        options = fixer.analyze_failure("story_schema", {"content": "", "missing_sections": [], "file_path": file_path})
    
    assert len(options) == 1
    assert options[0]['title'] == 'Fix 1'
    assert options[0]['description'] == 'Desc 1'

def test_analyze_failure_extracts_markdown_json(fixer, tmp_path, monkeypatch):
    """Test extracting JSON wrapped in markdown code blocks."""
    monkeypatch.chdir(tmp_path)
    # Create dummy file
    p = tmp_path / "test.md"
    p.write_text("content")
    file_path = str(p)

    mock_response = '''
    Here is the fix:
    ```json
    [
        {"title": "Fix Markdown", "description": "Desc", "patched_content": "fixed"}
    ]
    ```
    Hope this helps!
    '''
    
    with patch.object(fixer.ai, 'get_completion', return_value=mock_response):
        options = fixer.analyze_failure("story_schema", {"content": "", "missing_sections": [], "file_path": file_path})
        
    assert len(options) == 1
    assert options[0]['title'] == 'Fix Markdown'
    assert options[0]['description'] == 'Desc'

def test_analyze_failure_extracts_json_with_chatter(fixer, tmp_path, monkeypatch):
    """Test extracting JSON array surrounded by text without markdown blocks."""
    monkeypatch.chdir(tmp_path)
    # Create dummy file
    p = tmp_path / "test.md"
    p.write_text("content")
    file_path = str(p)

    mock_response = '''
    Sure, I can help with that.
    [
        {
            "title": "Chatter Fix",
            "description": "Desc",
            "patched_content": "fixed"
        }
    ]
    Let me know if you need anything else.
    '''
    
    with patch.object(fixer.ai, 'get_completion', return_value=mock_response):
        options = fixer.analyze_failure("story_schema", {"content": "", "missing_sections": [], "file_path": file_path})
        
    assert len(options) == 1
    assert options[0]['title'] == 'Chatter Fix'
    assert options[0]['description'] == 'Desc'

def test_analyze_failure_handles_newlines_in_strings(fixer, tmp_path, monkeypatch):
    """Test extracting JSON with literal newlines in strings (common AI artifact)."""
    monkeypatch.chdir(tmp_path)
    # Create dummy file
    p = tmp_path / "test.md"
    p.write_text("content")
    file_path = str(p)

    # Note: strict=False in json.loads allows control characters
    mock_response = '''
    [
        {
            "title": "Multiline Fix",
            "description": "Line 1\nLine 2",
            "patched_content": "fixed"
        }
    ]
    '''
    
    with patch.object(fixer.ai, 'get_completion', return_value=mock_response):
        options = fixer.analyze_failure("story_schema", {"content": "", "missing_sections": [], "file_path": file_path})
        
    assert len(options) == 1
    assert "Line 1\nLine 2" in options[0]["description"]

def test_analyze_failure_handles_malformed_json(fixer, tmp_path, monkeypatch):
    """Test that truly malformed JSON triggers the fallback log but doesn't crash."""
    monkeypatch.chdir(tmp_path)
    # Create dummy file
    p = tmp_path / "test.md"
    p.write_text("content")
    file_path = str(p)

    mock_response = "I cannot generate a fix for this."
    
    with patch.object(fixer.ai, 'get_completion', return_value=mock_response):
        # Should return empty list or raise ValueError depending on implementation
        # Current implementation catches JSONDecodeError and logs warning, returns empty valid_options?
        # WAIT: The implementation raises ValueError("AI response was not valid JSON.") inside analyze_failure
        # but the caller (cli) might catch it? 
        # Actually analyze_failure catches Exception and returns Manual Fix option at the top level?
        # Let's verify analyze_failure logic.
        
        # fix_story tool catches exceptions? No, analyze_failure has a try/except block?
        # Viewing fixer.py: analyze_failure HAS a try...except Exception block that returns Manual Fix.
        
        options = fixer.analyze_failure("story_schema", {"content": "", "missing_sections": [], "file_path": file_path})
        
    assert len(options) == 1
    assert options[0]["title"] == "Manual Fix (Open in Editor)"
