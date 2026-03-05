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

"""Tests for configurable console personality prompt (INFRA-097).

Verifies the three-layer prompt composition:
  1. console.system_prompt (personality preamble)
  2. console.personality_file (repo context file content)
  3. Runtime context (repo name, license header, project layout)

And the fallback to the hardcoded 'clinical' prompt when no config is set.
"""

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tui import app


@pytest.fixture(autouse=True)
def reset_prompt_cache():
    """Reset the cached system prompt before each test."""
    app._CACHED_SYSTEM_PROMPT = None
    yield
    app._CACHED_SYSTEM_PROMPT = None


def _make_config(system_prompt=None, personality_file=None, repo_root="/tmp/test-repo"):
    """Create a mock config with console settings."""
    mock = MagicMock()
    mock.repo_root = Path(repo_root)
    mock.templates_dir = Path(repo_root) / ".agent" / "templates"
    mock.console.system_prompt = system_prompt
    mock.console.personality_file = personality_file
    return mock


class TestFallbackBehavior:
    """When no console config is set, the original clinical prompt is used."""

    def test_no_console_config_returns_clinical_prompt(self):
        """AC-2: Fallback to existing hardcoded prompt when config is missing."""
        cfg = _make_config()
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "expert agentic development assistant" in prompt
            assert "test-repo" in prompt

    def test_empty_strings_treated_as_no_config(self):
        """Empty strings for both keys should trigger fallback."""
        cfg = _make_config(system_prompt="", personality_file="")
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "expert agentic development assistant" in prompt


class TestCustomPersonality:
    """When console config is set, the layered prompt is used."""

    def test_system_prompt_only(self):
        """AC-1: system_prompt appears in the output."""
        cfg = _make_config(system_prompt="You are a collaborative pair-programmer.")
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "collaborative pair-programmer" in prompt
            assert "Repository Context" in prompt
            # Should NOT contain the clinical fallback
            assert "expert agentic development assistant" not in prompt

    def test_personality_file_loaded(self, tmp_path):
        """AC-1: personality_file content is loaded and included."""
        persona_file = tmp_path / "GEMINI.md"
        persona_file.write_text("# Agentic Dev\nUse strict workflows.")

        cfg = _make_config(
            system_prompt="Be collaborative.",
            personality_file="GEMINI.md",
            repo_root=str(tmp_path),
        )
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "Be collaborative." in prompt
            assert "Agentic Dev" in prompt
            assert "Use strict workflows." in prompt

    def test_system_prompt_and_file_layered(self, tmp_path):
        """Both layers appear in order: system_prompt, then file content, then runtime."""
        persona_file = tmp_path / "personality.md"
        persona_file.write_text("## Repo Rules\nFollow the rules.")

        cfg = _make_config(
            system_prompt="Layer one preamble.",
            personality_file="personality.md",
            repo_root=str(tmp_path),
        )
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            preamble_pos = prompt.index("Layer one preamble")
            file_pos = prompt.index("Repo Rules")
            runtime_pos = prompt.index("Repository Context")
            assert preamble_pos < file_pos < runtime_pos


class TestPathTraversal:
    """Security: personality_file must resolve within repo root."""

    def test_path_traversal_rejected(self, tmp_path):
        """AC-3: ../../etc/passwd must not be loaded."""
        cfg = _make_config(
            system_prompt="Safe prompt.",
            personality_file="../../etc/passwd",
            repo_root=str(tmp_path),
        )
        with patch("agent.core.config.config", cfg), \
             patch("agent.tui.app.logger") as mock_logger:
            prompt = app._build_system_prompt()
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert "system_prompt.path_rejected" in str(call_args)
            assert "passwd" not in prompt

    def test_missing_personality_file_graceful(self, tmp_path):
        """Missing personality_file should not crash, just skip."""
        cfg = _make_config(
            system_prompt="Still works.",
            personality_file="DOES_NOT_EXIST.md",
            repo_root=str(tmp_path),
        )
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "Still works." in prompt
            assert "Repository Context" in prompt


class TestRuntimeContext:
    """Runtime context (repo info, license, project layout) is always included."""

    def test_project_layout_in_custom_prompt(self, tmp_path):
        """Project layout tree appears in custom prompt."""
        cfg = _make_config(system_prompt="Custom.", repo_root=str(tmp_path))
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "Project Layout" in prompt
            assert ".agent/" in prompt

    def test_license_header_in_custom_prompt(self, tmp_path):
        """License header is included when template file exists."""
        templates_dir = tmp_path / ".agent" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "license_header.txt").write_text("Copyright 2026 Test Corp")

        cfg = _make_config(system_prompt="Custom.", repo_root=str(tmp_path))
        with patch("agent.core.config.config", cfg):
            prompt = app._build_system_prompt()
            assert "Copyright 2026 Test Corp" in prompt
            assert "Required License Header" in prompt