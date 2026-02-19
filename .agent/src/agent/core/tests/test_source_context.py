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

"""Tests for source code context loading in ContextLoader."""

import pytest
from unittest.mock import patch

from agent.core.context import ContextLoader


@pytest.fixture
def mock_src_tree(tmp_path):
    """Create a mock source directory structure under tmp_path/src/."""
    src = tmp_path / "src" / "agent"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("# small init")

    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("# small init")
    (core / "config.py").write_text(
        "import yaml\nfrom pathlib import Path\n\n"
        "class Config:\n    def __init__(self):\n        pass\n\n"
        "    def get(self, key):\n        pass\n"
    )

    ai = core / "ai"
    ai.mkdir()
    (ai / "__init__.py").write_text("# small init")
    (ai / "service.py").write_text(
        "from google import genai\nimport os\n\n"
        "class AIService:\n    def complete(self, system, user):\n        pass\n\n"
        "    def reload(self):\n        pass\n"
    )

    # __pycache__ should be excluded
    cache = core / "__pycache__"
    cache.mkdir()
    (cache / "config.cpython-312.pyc").write_text("bytecode")

    # .env file should be excluded
    (src / ".env").write_text("SECRET_KEY=hunter2")

    return tmp_path


@pytest.fixture
def empty_src(tmp_path):
    """Create a src/ directory with no .py files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / ".gitkeep").write_text("")
    return tmp_path


@pytest.fixture
def no_src(tmp_path):
    """tmp_path with no src/ directory at all."""
    return tmp_path


class TestLoadSourceTree:
    def test_returns_tree_with_real_files(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            tree = loader._load_source_tree()

        assert "config.py" in tree
        assert "service.py" in tree
        assert "SOURCE FILE TREE:" in tree

    def test_excludes_pycache(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            tree = loader._load_source_tree()

        assert "__pycache__" not in tree
        assert ".pyc" not in tree

    def test_excludes_env_files(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            tree = loader._load_source_tree()

        assert ".env" not in tree
        assert "SECRET_KEY" not in tree

    def test_returns_empty_when_no_src(self, no_src):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = no_src
            assert loader._load_source_tree() == ""

    def test_returns_tree_for_empty_src(self, empty_src):
        """Edge case: src/ exists but has no .py files (@QA advice)."""
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = empty_src
            tree = loader._load_source_tree()

        # Should still produce a tree header with the directory name
        assert "SOURCE FILE TREE:" in tree
        assert "src/" in tree


class TestLoadSourceSnippets:
    def test_extracts_class_and_function_signatures(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            snippets = loader._load_source_snippets()

        assert "class Config" in snippets
        assert "class AIService" in snippets
        assert "def complete" in snippets
        assert "from google import genai" in snippets

    def test_respects_budget(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            snippets = loader._load_source_snippets(budget=100)

        # Should be truncated
        assert "[...truncated...]" in snippets

    def test_respects_env_var_budget(self, mock_src_tree, monkeypatch):
        """Verify AGENT_SOURCE_CONTEXT_CHAR_LIMIT env var is wired through (@Architect advice)."""
        monkeypatch.setenv("AGENT_SOURCE_CONTEXT_CHAR_LIMIT", "100")
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            snippets = loader._load_source_snippets()  # budget=0 -> reads env var

        assert "[...truncated...]" in snippets

    def test_returns_empty_when_no_src(self, no_src):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = no_src
            assert loader._load_source_snippets() == ""

    def test_empty_src_returns_header_only(self, empty_src):
        """Edge case: src/ exists but has no .py files (@QA advice)."""
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = empty_src
            snippets = loader._load_source_snippets()

        assert snippets == "SOURCE CODE OUTLINES:\n"


class TestLoadContextIncludesSource:
    def test_context_has_source_keys(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            mock_config.rules_dir = mock_src_tree / "rules"
            mock_config.etc_dir = mock_src_tree / "etc"
            mock_config.instructions_dir = mock_src_tree / "instructions"
            ctx = loader.load_context()

        assert "source_tree" in ctx
        assert "source_code" in ctx
        assert "rules" in ctx
        assert "adrs" in ctx

    def test_source_tree_is_nonempty_with_sources(self, mock_src_tree):
        loader = ContextLoader()
        with patch("agent.core.context.config") as mock_config:
            mock_config.agent_dir = mock_src_tree
            mock_config.rules_dir = mock_src_tree / "rules"
            mock_config.etc_dir = mock_src_tree / "etc"
            mock_config.instructions_dir = mock_src_tree / "instructions"
            ctx = loader.load_context()

        assert len(ctx["source_tree"]) > 0
        assert "config.py" in ctx["source_tree"]
