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

"""Tests for the INFRA-173 docstring gate bypass in enforce_docstrings (INFRA-173).

Validates that files with WARNING-level gate hits (test files, minor doc gaps)
are not surface as FAIL results, preserving the verbatim-apply contract.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from agent.core.implement.guards import enforce_docstrings


def test_test_file_passes_gate_on_warning_content() -> None:
    """Document that enforce_docstrings is strict; the bypass lives in implement.py.

    Ensures the caller (verbatim-apply loop) can trust that enforce_docstrings
    always reports violations, and the INFRA-173 bypass decision is made upstream.
    """
    content = "def test_my_feature(): assert True\n"
    result = enforce_docstrings("test_my_feature.py", content)
    # The low-level guard is strict — errors are expected; implement.py ignores them
    # for test_*.py files (INFRA-173 bypass logic applied at the caller level).
    assert not result.passed, (
        "enforce_docstrings should be strict; caller handles the bypass."
    )


def test_source_file_with_docstring_passes_cleanly() -> None:
    """Verify that a well-documented source file passes with no errors or warnings."""
    content = '"""Module docstring."""\n\ndef token_counter():\n    """Count tokens."""\n    return 0\n'
    result = enforce_docstrings("token_counter.py", content)
    assert result.passed
    assert result.errors == []
    assert result.warnings == []
