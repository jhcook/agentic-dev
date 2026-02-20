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
import os
from typer.testing import CliRunner
from unittest.mock import patch
from agent.main import app

@pytest.fixture
def temp_repo(tmp_path):
    """
    Creates a temporary repo structure with a valid config and a broken story.
    """
    # 1. Setup minimal .agent structure
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()
    (agent_dir / "src").mkdir()
    
    # 2. Config
    config_dir = agent_dir / "etc"
    config_dir.mkdir(parents=True)
    (config_dir / "agent.yaml").write_text("agent:\n  provider: gh\n")
    
    # 3. Create a broken story
    stories_dir = agent_dir / "cache" / "stories" / "INFRA"
    stories_dir.mkdir(parents=True)
    story_file = stories_dir / "INFRA-E2E-001-broken-story.md"
    story_file.write_text("# Broken Story\n\nMissing Sections")
    
    return tmp_path, story_file

runner = CliRunner()


def test_interactive_preflight_typer_e2e(temp_repo):
    """
    Simulate E2E using Typer's CliRunner with mocked AI service.
    """
    repo_root, story_file = temp_repo
    
    # Patch Config to point to temp_repo
    with patch("agent.core.config.config.repo_root", repo_root), \
         patch("agent.core.config.config.stories_dir", story_file.parent.parent.parent), \
         patch("agent.core.ai.ai_service") as mock_ai, \
         patch("agent.core.fixer.ai_service") as mock_fixer_ai, \
         patch("agent.core.fixer.Path.cwd") as mock_cwd, \
         patch("agent.sync.notion.NotionSync"), \
         patch("subprocess.run") as mock_run:
             
        # Configure CWD to match temp_repo
        mock_cwd.return_value = repo_root
        mock_cwd.side_effect = None 
        
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Tests Passed" 
        
        # Verify Path usage in fixer.py: `path = Path(file_path).resolve()`
        # `repo_root = Path.cwd().resolve()`
        # repo_root is a real Path object, so .resolve() returns itself. No need to mock.
             
        # Setup Mock AI Response for Fixer
        mock_fixer_ai.get_completion.return_value = """
        [
            {
                "title": "Fix Schema",
                "description": "Adds missing sections",
                "patched_content": "## Problem Statement\\nFixed\\n## User Story\\n...\\n## Acceptance Criteria\\n...\\n## Non-Functional Requirements\\n...\\n## Impact Analysis Summary\\n...\\n## Test Strategy\\n...\\n## Rollback Plan\\n...\\n## Linked Journeys\\n- JRN-001\\n"
            }
        ]
        """
        
        # We need to ensure `validate_story` finds the file in our temp structure
        # The `validate_story` uses `config.stories_dir.rglob`.
        # We patched `config.stories_dir` to `tmp_path/.agent/cache/stories`.
        # rglob(INFRA-E2E...) should find it.
        
        # Input: "1" to select option, "y" to confirm apply
        result = runner.invoke(app, ["preflight", "--interactive", "--story", "INFRA-E2E-001"], input="1\ny\n")
        
        # Output Debugging
        print(result.stdout)
        
        # Assertions
        assert result.exit_code == 0
        assert "Story schema validation failed" in result.stdout
        assert "Fix Options" in result.stdout
        assert "Applied fix" in result.stdout
        assert "Verification Passed" in result.stdout

def test_interactive_preflight_empty_ai_response(temp_repo):
    """
    Simulate scenario where AI returns empty/invalid response.
    Should handle gracefully without crashing.
    """
    repo_root, story_file = temp_repo
    
    with patch("agent.core.config.config.repo_root", repo_root), \
         patch("agent.core.config.config.stories_dir", story_file.parent.parent.parent), \
         patch("agent.core.ai.ai_service") as mock_ai, \
         patch("agent.core.fixer.ai_service") as mock_fixer_ai, \
         patch("agent.sync.notion.NotionSync"), \
         patch("agent.core.fixer.Path.cwd") as mock_cwd:
             
        mock_cwd.return_value = repo_root
        
        # Simulate Empty Response
        mock_fixer_ai.get_completion.return_value = ""
        
        # We expect it to fail generating options, log the error, and probably exit or print a message
        # In current check.py impl, it catches ValueError and prints "Failed to generate fix options"
        
        result = runner.invoke(app, ["preflight", "--interactive", "--story", "INFRA-E2E-001"])
        
        print(result.stdout)
        
        # It shouldn't crash (exit 0 from Typer even if internal check failed, or non-zero handled)
        # check.py returns False on failure
        # The key is that it doesn't raise Unhandled Exception
        
        assert "Story schema validation failed" in result.stdout
        assert "Manual Fix (Open in Editor)" in result.stdout
        assert "AI generation failed" in result.stdout

def test_interactive_preflight_voice_mode(temp_repo):
    """
    Simulate Voice Mode (AGENT_VOICE_MODE=1) and ensure output is formatted for TTS.
    """
    repo_root, story_file = temp_repo
    
    with patch("agent.core.config.config.repo_root", repo_root), \
         patch("agent.core.config.config.stories_dir", story_file.parent.parent.parent), \
         patch("agent.core.ai.ai_service") as mock_ai, \
         patch("agent.core.fixer.ai_service") as mock_fixer_ai, \
         patch("agent.core.fixer.Path.cwd") as mock_cwd, \
         patch("subprocess.run") as mock_run, \
         patch("agent.sync.notion.NotionSync"), \
         patch.dict(os.environ, {"AGENT_VOICE_MODE": "1"}):
             
        mock_cwd.return_value = repo_root
        
        # Mock subprocess run to simulate successful test execution
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Tests Passed"
        
        # Valid Fix Options
        mock_fixer_ai.get_completion.return_value = """
        [
            {
                "title": "Voice Fix",
                "description": "Voice friendly description",
                "patched_content": "## Problem Statement\\nFixed\\n## User Story\\n...\\n## Acceptance Criteria\\n...\\n## Non-Functional Requirements\\n...\\n## Impact Analysis Summary\\n...\\n## Test Strategy\\n...\\n## Rollback Plan\\n...\\n## Linked Journeys\\n- JRN-001\\n"
            }
        ]
        """
        
        # Input: "1" to select, "y" to confirm (Voice agent maps speech to these keys)
        result = runner.invoke(app, ["preflight", "--interactive", "--story", "INFRA-E2E-001"], input="1\ny\n")
        
        print(result.stdout)
        
        # Assertions for Voice-Specific Output
        # 1. "Found the following fix options:" instead of "🔧 Fix Options:"
        assert "Found the following fix options:" in result.stdout
        assert "🔧 Fix Options:" not in result.stdout
        
        # 2. "Option 1: Voice Fix. Voice friendly description" (Single line)
        assert "Option 1: Voice Fix. Voice friendly description" in result.stdout
        
        # 3. "Select an option (or say quit):" instead of "Select an option (or 'q' to quit)"
        assert "Select an option (or say quit):" in result.stdout
        
        assert result.exit_code == 0
