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

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.context import ContextLoader


@pytest.fixture
def loader() -> ContextLoader:
    """Return a ContextLoader instance for testing."""
    return ContextLoader()


def test_load_targeted_context_happy_path(loader: ContextLoader, tmp_path: Path) -> None:
    """Given a story with a [MODIFY] file annotation, _load_targeted_context returns actual signatures."""
    with patch("agent.core.context.config") as mock_config:
        mock_config.agent_dir = tmp_path
        mock_config.repo_root = tmp_path

        # Create a dummy file at the canonical src/ path
        src_dir = tmp_path / "src" / "core" / "ai"
        src_dir.mkdir(parents=True)
        test_file = src_dir / "service.py"
        test_file.write_text("import os\n\ndef my_func():\n    pass\n")

        story = "#### [MODIFY] core/ai/service.py"
        result = loader._load_targeted_context(story)

        assert "TARGETED FILE CONTENTS" in result
        assert "core/ai/service.py" in result
        assert "def my_func()" in result
        assert "import os" in result


def test_load_targeted_context_file_not_found(loader: ContextLoader, tmp_path: Path) -> None:
    """Given a story referencing a nonexistent file, _load_targeted_context emits FILE NOT FOUND."""
    with patch("agent.core.context.config") as mock_config:
        mock_config.agent_dir = tmp_path
        mock_config.repo_root = tmp_path
        story = "#### [MODIFY] non_existent.py"
        result = loader._load_targeted_context(story)
        assert "FILE NOT FOUND" in result


def test_load_targeted_context_empty_story(loader: ContextLoader) -> None:
    """Given empty story content, _load_targeted_context returns only the header."""
    result = loader._load_targeted_context("")
    assert "TARGETED FILE CONTENTS" in result
    # Should only contain header if no matches


def test_load_test_impact_finds_patches(loader: ContextLoader, tmp_path: Path) -> None:
    """Given a test file with a patch() target for a story module, _load_test_impact reports it."""
    with patch("agent.core.context.config") as mock_config:
        mock_config.agent_dir = tmp_path

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_service.py"
        test_file.write_text('with patch("agent.core.ai.service.AIService"): pass')

        story = "Modifying core/ai/service.py"
        result = loader._load_test_impact(story)

        assert "TEST IMPACT MATRIX" in result
        assert "test_service.py" in result
        assert 'patch("agent.core.ai.service.AIService")' in result


def test_load_test_impact_no_tests_dir(loader: ContextLoader, tmp_path: Path) -> None:
    """Given a missing tests directory, _load_test_impact returns a graceful header-only result."""
    with patch("agent.core.context.config") as mock_config:
        mock_config.agent_dir = tmp_path
        result = loader._load_test_impact("some story")
        assert "No tests directory found" in result


def test_load_behavioral_contracts_extracts_defaults(loader: ContextLoader, tmp_path: Path) -> None:
    """Given tests with assert and default parameter patterns, _load_behavioral_contracts extracts them."""
    with patch("agent.core.context.config") as mock_config:
        mock_config.agent_dir = tmp_path

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_service.py"
        test_file.write_text('assert auto_fallback == True\ncall(default_val=10)')

        story = "Fixing service.py"
        result = loader._load_behavioral_contracts(story)

        assert "BEHAVIORAL CONTRACTS" in result
        assert "assert auto_fallback == True" in result
        assert "default_val=10" in result