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

"""Tests for path resolution logic in the implement orchestrator (INFRA-109)."""

import pytest
import logging
from pathlib import Path
from unittest.mock import patch
from agent.core.implement.orchestrator import resolve_path, TRUSTED_ROOT_PREFIXES

def test_resolve_path_trusted_prefix_ac1():
    """AC-1: Paths with trusted prefixes should be returned as-is without fuzzy matching."""
    path = ".agent/tests/core/implement/test_orchestrator.py"
    with patch("agent.core.implement.orchestrator._find_file_in_repo") as mock_find:
        result = resolve_path(path)
        assert result == Path(path)
        mock_find.assert_not_called()

def test_resolve_path_fuzzy_match_non_trusted_ac2():
    """AC-2: Non-trusted paths should still use fuzzy matching with a log warning."""
    path = "test_orchestrator.py"
    expected = ".agent/tests/core/implement/test_orchestrator.py"
    
    with patch("agent.core.implement.orchestrator._find_file_in_repo", return_value=[expected]):
        with patch("agent.core.implement.orchestrator.logging") as mock_logging:
            result = resolve_path(path)
            assert result == Path(expected)
            mock_logging.warning.assert_called_once()
            _, kwargs = mock_logging.warning.call_args
            assert kwargs["extra"]["original_path"] == path
            assert kwargs["extra"]["resolved_path"] == expected

def test_resolve_path_no_match_ac2():
    """Ensure non-trusted paths with no match are returned as-is."""
    path = "non_existent_script.py"
    with patch("agent.core.implement.orchestrator._find_file_in_repo", return_value=[]):
        with patch("agent.core.implement.orchestrator._find_directories_in_repo", return_value=[]):
            result = resolve_path(path)
            assert result == Path(path)

@pytest.mark.parametrize("prefix", [p for p in TRUSTED_ROOT_PREFIXES])
def test_all_trusted_prefixes(prefix):
    """Ensure all prefixes in TRUSTED_ROOT_PREFIXES trigger the short-circuit."""
    path = f"{prefix}some/file.txt"
    with patch("agent.core.implement.orchestrator._find_file_in_repo") as mock_find:
        result = resolve_path(path)
        assert result == Path(path)
        mock_find.assert_not_called()