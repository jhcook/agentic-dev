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

"""Unit tests for INFRA-155: Gate relaxation and import validation."""

import pytest
from agent.core.implement.guards import enforce_docstrings, check_imports, validate_code_block

def test_enforce_docstrings_nesting():
    """Verify that nested functions only trigger warnings, while top-level trigger errors."""
    content = '''"""Module docstring."""
def top_level():
    """Valid docstring."""
    def nested_no_doc():
        pass
    return True

def top_level_no_doc():
    pass
'''
    res = enforce_docstrings("test.py", content)
    # top_level_no_doc should be an error
    assert any("top_level_no_doc() is missing a docstring" in e for e in res.errors)
    # nested_no_doc should be a warning
    assert any("nested function nested_no_doc() is missing a docstring" in w for w in res.warnings)
    # No error for nested
    assert not any("nested_no_doc() is missing a docstring" in e for e in res.errors)

def test_check_imports_undeclared():
    """Verify that undeclared dependencies are flagged."""
    content = "import os\nimport some_weird_package\nfrom agent.core import utils"
    # Assuming 'some_weird_package' is not in pyproject.toml
    res = check_imports("test.py", content)
    assert any("undeclared dependency 'some_weird_package'" in e for e in res.errors)
    assert not any("undeclared dependency 'os'" in e for e in res.errors)
    assert not any("undeclared dependency 'agent'" in e for e in res.errors)

def test_validate_code_block_normalisies_trailing_newline() -> None:
    """Verify validate_code_block normalises missing trailing newline (parser artefact).

    parse_code_blocks always strips trailing whitespace, so validate_code_block
    must not treat the missing newline as a gate error or it would false-positive
    on every extracted code block during runbook self-healing.
    """
    # Content without trailing newline (as parse_code_blocks produces)
    content_no_newline = '"""Module."""\n\n\ndef foo() -> None:\n    """Foo."""\n    pass'
    res = validate_code_block("test.py", content_no_newline)
    assert not res.errors, f"Unexpected errors: {res.errors}"

    # Content with trailing newline (as direct file write produces) also passes
    content_with_newline = content_no_newline + "\n"
    res_ok = validate_code_block("test.py", content_with_newline)
    assert not res_ok.errors