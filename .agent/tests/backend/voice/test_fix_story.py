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
from unittest.mock import MagicMock, patch
from backend.voice.tools.fix_story import interactive_fix_story

MOCK_REPO = Path("/mock/repo")

@pytest.fixture
def mock_deps(tmp_path):
    """Set up mocks for fix_story tests using repo_root parameter."""

    with patch('backend.voice.tools.fix_story.subprocess.Popen') as mock_popen, \
         patch('backend.voice.tools.fix_story.EventBus') as mock_bus, \
         patch('agent.core.fixer.ai_service') as mock_ai, \
         patch('agent.core.fixer.Path') as mock_path_cls, \
         patch('agent.core.fixer.shutil') as mock_shutil, \
         patch('agent.core.fixer.tempfile') as mock_tempfile, \
         patch('agent.core.fixer.os') as mock_os:
        
        # Bypass security check by mocking Path in fixer module only
        mock_cwd_path = MagicMock()
        mock_cwd_path.__str__.return_value = "/mock/repo"
        mock_cwd_path.resolve.return_value = mock_cwd_path
        
        mock_file_path = MagicMock()
        mock_file_path.__str__.return_value = "/mock/repo/WEB-001.md"
        mock_file_path.read_text.return_value = "Old Content"
        mock_file_path.resolve.return_value = mock_file_path
        mock_file_path.exists.return_value = True
        
        def path_side_effect(*args, **kwargs):
            if not args:
                 return MagicMock()
            arg = str(args[0])
            if "WEB-001" in arg:
                return mock_file_path
            return mock_cwd_path
            
        mock_path_cls.side_effect = path_side_effect
        mock_path_cls.cwd.return_value = mock_cwd_path
        
        mock_tempfile.mkstemp.return_value = (123, "/tmp/backup")
        mock_os.path.commonpath.return_value = "/mock/repo"
        
        # Create a mock stories_dir with rglob
        stories_dir = MOCK_REPO / ".agent" / "cache" / "stories"
        
        yield mock_popen, mock_bus, mock_ai, stories_dir

@pytest.fixture
def mock_session():
    with patch('backend.voice.tools.fix_story.get_session_id', return_value='s1'):
        yield

def test_analyze_mode_integration(mock_deps, mock_session, tmp_path):
    """Test full flow from tool -> fixer -> options (using mocked AI)."""
    mock_popen, mock_bus, mock_ai, stories_dir = mock_deps
    
    # 1. Validation fails
    process_mock = mock_popen.return_value
    process_mock.returncode = 1
    process_mock.communicate.return_value = ("Missing sections: Problem Statement", "")
    
    # 2. File exists - mock the rglob on the stories_dir path
    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    with patch.object(Path, 'rglob', return_value=[mock_path]):
        # 3. AI Returns Valid JSON
        mock_ai.get_completion.return_value = '[{"title": "Real Fix", "description": "AI generated", "patched_content": "new content"}]'
        
        result = interactive_fix_story("WEB-001", repo_root=MOCK_REPO)
    
    assert "Found 1 options" in result
    assert "Real Fix" in result

def test_apply_mode_integration(mock_deps, mock_session, tmp_path):
    """Test applying a fix writes to file and verifies."""
    mock_popen, mock_bus, mock_ai, stories_dir = mock_deps
    
    p1 = MagicMock()
    p1.returncode = 1
    p1.communicate.return_value = ("Missing sections: Problem Statement", "")
    
    p2 = MagicMock()
    p2.returncode = 0
    p2.communicate.return_value = ("OK", "")
    
    mock_popen.side_effect = [p1, p2]

    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    mock_path.read_text.return_value = "Old Content"
    
    with patch.object(Path, 'rglob', return_value=[mock_path]):
        mock_ai.get_completion.return_value = '[{"title": "Fix It", "description": "desc", "patched_content": "New Content"}]'
        
        result = interactive_fix_story("WEB-001", repo_root=MOCK_REPO, apply_idx=1)
    
    assert "Successfully applied fix" in result
    assert "Fix It" in result
    mock_path.write_text.assert_called_with("New Content")

def test_invalid_index_error(mock_deps, mock_session):
    mock_popen, mock_bus, mock_ai, stories_dir = mock_deps
    
    process_mock = mock_popen.return_value
    process_mock.returncode = 1
    process_mock.communicate.return_value = ("Missing: X", "")
    
    mock_path = MagicMock()
    mock_path.name = "WEB-001-story.md"
    
    with patch.object(Path, 'rglob', return_value=[mock_path]):
        mock_ai.get_completion.return_value = '[{"title": "Fix", "patched_content": "C"}]'
        
        result = interactive_fix_story("WEB-001", repo_root=MOCK_REPO, apply_idx=99)
    
    assert "Invalid option index" in result

def test_missing_story_file(mock_session):
    with patch.object(Path, 'rglob', return_value=[]):
        result = interactive_fix_story("UNKNOWN-001", repo_root=MOCK_REPO)
    
    assert "Could not find story file" in result
