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

"""Tests for resolve_repo_path() CWD-independence (INFRA-138)."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, PropertyMock

from agent.core.config import resolve_repo_path, config


class TestResolveRepoPath:
    """AC-6: Verify resolver works from any CWD."""

    def test_resolves_against_repo_root(self):
        """Path resolves against config.repo_root, not os.getcwd()."""
        result = resolve_repo_path(".agent/src/agent/core/config.py")
        assert result == (config.repo_root / ".agent/src/agent/core/config.py").resolve()
        assert result.is_absolute()

    def test_returns_absolute_path(self):
        """Resolved path is always absolute."""
        result = resolve_repo_path(".agent/etc/agents.yaml")
        assert result.is_absolute()

    def test_traversal_rejected_ac7(self):
        """AC-7: Path with .. traversal raises ValueError."""
        with pytest.raises(ValueError, match="traversal"):
            resolve_repo_path("../escape/attempt")

    def test_double_dot_in_middle_rejected(self):
        """AC-7: Path with .. in middle raises ValueError."""
        with pytest.raises(ValueError, match="traversal"):
            resolve_repo_path(".agent/../../../etc/passwd")

    def test_absolute_path_rejected_ac7(self):
        """AC-7: Absolute paths raise ValueError."""
        with pytest.raises(ValueError, match="Absolute"):
            resolve_repo_path("/etc/passwd")

    def test_cwd_independent(self, tmp_path, monkeypatch):
        """Resolver returns same result regardless of CWD."""
        result_from_root = resolve_repo_path(".agent/etc/agents.yaml")
        monkeypatch.chdir(tmp_path)
        result_from_tmp = resolve_repo_path(".agent/etc/agents.yaml")
        assert result_from_root == result_from_tmp
