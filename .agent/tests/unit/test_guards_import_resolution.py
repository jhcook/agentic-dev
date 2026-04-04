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
from agent.core.implement.guards import check_test_imports_resolvable

def test_check_test_imports_resolvable_cross_block():
    """AC-2: Verify that imports defined in other blocks in the same runbook pass."""
    content = "from agent.core.foo import MyClass\n"
    # Symbol 'MyClass' is simulated as being present in the runbook session index
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, {"MyClass"})
    assert result is None

def test_check_test_imports_resolvable_stdlib():
    """AC-3: Verify that Python standard library imports pass validation."""
    content = "import os\nfrom pathlib import Path\nimport typing\n"
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_type_checking():
    """AC-4: Verify that imports inside if TYPE_CHECKING blocks are ignored."""
    content = """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agent.missing.module import GhostSymbol

def test_logic():
    pass
"""
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_ignores_non_test_files():
    """AC-5: Verify that the gate only applies to files matching test naming patterns."""
    content = "from agent.missing import Ghost\n"
    # Path does not contain 'tests/' and name does not start with 'test_'
    result = check_test_imports_resolvable(Path("agent/core/logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_unresolved_error():
    """AC-1: Verify that unresolvable imports in a test file return a correction prompt."""
    content = "from agent.core.logic import NonExistentSymbol\n"
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is not None
    assert "IMPORT RESOLUTION FAILURE" in result
    assert "agent.core.logic.NonExistentSymbol" in result
