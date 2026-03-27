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

import os
from pathlib import Path
import pytest

"""Programmatic verification of INFRA-171 test consolidation."""

# Anchor to repo root: this file is at .agent/tests/agent/core/governance/test_*.py
REPO_ROOT = Path(__file__).resolve().parents[5]

def test_no_colocated_tests_in_src():
    """Verify that no directory named 'tests' exists within the agent Python package."""
    src_root = REPO_ROOT / ".agent" / "src" / "agent"
    violations = []
    for root, dirs, files in os.walk(src_root):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        if "tests" in dirs:
            test_dir = os.path.join(root, "tests")
            # Only flag if it contains actual test files (not empty stubs)
            test_files = [f for f in os.listdir(test_dir)
                         if f.startswith("test_") and f.endswith(".py")]
            if test_files:
                violations.append(test_dir)
    
    assert not violations, f"Architectural Violation: Colocated tests found at {violations}"

def test_test_discovery_count():
    """Verify that pytest discovers the expected hierarchy under .agent/tests."""
    test_root = REPO_ROOT / ".agent" / "tests" / "agent"
    # We expect at least the migrated subdirectories to exist and contain files
    required_dirs = ["commands", "core/engine", "core/governance", "core/implement", "tools", "utils"]
    for d in required_dirs:
        full_path = test_root / d
        assert full_path.is_dir(), f"Missing consolidated test directory: {full_path}"
        # Ensure it's not empty (should contain test_*.py files)
        files = list(full_path.glob("test_*.py"))
        assert len(files) > 0, f"No tests discovered in {full_path}"

def test_absolute_import_resolution():
    """Verify that absolute imports for the agent package are functional post-migration."""
    try:
        from agent.core.utils import scrub_sensitive_data
        from agent.commands.decompose_story import get_next_ids
        assert scrub_sensitive_data is not None
        assert get_next_ids is not None
    except ImportError as e:
        pytest.fail(f"Absolute import failed: {e}. Migration refactoring may be incomplete.")

