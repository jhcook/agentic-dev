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
from backend.voice.tools.fix_story import interactive_fix_story

@pytest.fixture
def mock_deps():
    # Only mock external IO (subprocess, config, AI)
    # We use the REAL InteractiveFixer to test integration
    
    with patch('backend.voice.tools.fix_story.subprocess.Popen') as mock_popen, \
         patch('backend.voice.tools.fix_story.EventBus') as mock_bus, \
         patch('backend.voice.tools.fix_story.agent_config') as mock_config, \
         patch('agent.core.fixer.ai_service') as mock_ai, \
         patch('agent.core.fixer.Path') as mock_path_cls, \
         patch('agent.core.fixer.shutil') as mock_shutil, \
         patch('agent.core.fixer.tempfile') as mock_tempfile, \
         patch('agent.core.fixer.os') as mock_os:
        
        # Bypass security check by mocking Path in fixer module only
        # We need Path.cwd().resolve() to match Path(file).resolve() prefix
        
        mock_cwd_path = MagicMock()
        mock_cwd_path.__str__.return_value = "/mock/repo"
        mock_cwd_path.resolve.return_value = mock_cwd_path
        
        mock_file_path = MagicMock()
        mock_file_path.__str__.return_value = "/mock/repo/WEB-001.md"
        mock_file_path.read_text.return_value = "Old Content" # Default
        mock_file_path.resolve.return_value = mock_file_path
        mock_file_path.exists.return_value = True
        
        # Configure Path class mock
        def path_side_effect(*args, **kwargs):
            if not args:
                 return MagicMock()
            arg = str(args[0])
            if "WEB-001" in arg:
                return mock_file_path
            return mock_cwd_path
            
        mock_path_cls.side_effect = path_side_effect
        mock_path_cls.cwd.return_value = mock_cwd_path
        
        # Mock tempfile
        mock_tempfile.mkstemp.return_value = (123, "/tmp/backup")
        
        # Mock os
        mock_os.path.commonpath.return_value = "/mock/repo"
        
        # KEY FIX: subprocess.Popen(cwd=str(repo_root)) needs a string that isn't a MagicMock repr
        mock_config.repo_root.__str__.return_value = "/mock/repo"
        
        yield mock_popen, mock_bus, mock_config, mock_ai

def test_analyze_mode_integration(mock_deps):
    """Test full flow from tool -> fixer -> options (using mocked AI)."""
    mock_popen, mock_bus, mock_config, mock_ai = mock_deps
    
    # 1. Validation fails
    # Configure the Popen instance
    process_mock = mock_popen.return_value
    process_mock.returncode = 1
    process_mock.communicate.return_value = ("Missing sections: Problem Statement", "")
    
    # 2. File exists
    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    mock_config.stories_dir.rglob.return_value = [mock_path]
    
    # 3. AI Returns Valid JSON
    mock_ai.get_completion.return_value = '[{"title": "Real Fix", "description": "AI generated", "patched_content": "new content"}]'
    
    # Run Tool
    result = interactive_fix_story.func("WEB-001", config={"configurable": {"thread_id": "s1"}})
    
    # Verify
    assert "Found 1 options" in result
    assert "Real Fix" in result

def test_apply_mode_integration(mock_deps):
    """Test applying a fix writes to file and verifies."""
    mock_popen, mock_bus, mock_config, mock_ai = mock_deps
    
    # Setup Mocks for success/fail
    p1 = MagicMock()
    p1.returncode = 1
    p1.communicate.return_value = ("Missing sections: Problem Statement", "")
    
    p2 = MagicMock()
    p2.returncode = 0
    p2.communicate.return_value = ("OK", "")
    
    # Popen returns p1 then p2
    mock_popen.side_effect = [p1, p2]

    # 2. File Setup
    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    mock_path.read_text.return_value = "Old Content"
    mock_config.stories_dir.rglob.return_value = [mock_path]
    
    # 3. AI Setup
    mock_ai.get_completion.return_value = '[{"title": "Fix It", "description": "desc", "patched_content": "New Content"}]'
    
    # Run Tool (Apply index 1)
    result = interactive_fix_story.func("WEB-001", apply_idx=1, config={"configurable": {"thread_id": "s1"}})
    
    # Verify Result
    assert "Successfully applied fix" in result
    assert "Fix It" in result
    
    # Verify Write
    mock_path.write_text.assert_called_with("New Content")

def test_invalid_index_error(mock_deps):
    mock_popen, mock_bus, mock_config, mock_ai = mock_deps
    
    process_mock = mock_popen.return_value
    process_mock.returncode = 1
    process_mock.communicate.return_value = ("Missing: X", "")
    
    mock_config.stories_dir.rglob.return_value = [MagicMock()]
    mock_ai.get_completion.return_value = '[{"title": "Fix", "patched_content": "C"}]'
    
    # Apply index 99
    result = interactive_fix_story.func("WEB-001", apply_idx=99)
    assert "Invalid option index" in result

def test_missing_story_file(mock_deps):
    _, _, mock_config, _ = mock_deps
    mock_config.stories_dir.rglob.return_value = []
    
    result = interactive_fix_story.func("UNKNOWN-001")
    assert "Could not find story file" in result
