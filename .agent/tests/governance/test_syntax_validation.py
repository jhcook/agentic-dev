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

"""test_syntax_validation module."""

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
import py_compile
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.core.governance.syntax_validator import cross_validate_syntax_findings

"""Integration tests for syntax claim cross-validation."""

def test_dismisses_hallucinated_syntax_error(tmp_path):
    """Findings claiming syntax errors on valid files must be removed."""
    test_file = tmp_path / "app.py"
    test_file.write_text("def main():\n    print('hello')")
    
    findings = [
        "- Found a syntax error in app.py at line 2. (Source: app.py)",
        "- Missing docstring in app.py. (Source: app.py)"
    ]

    # Mock Path.cwd to find our temp file
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        # py_compile.compile succeeds by default for valid text
        validated = cross_validate_syntax_findings(findings)
        
        # Syntax claim should be gone, docstring claim remains
        assert len(validated) == 1
        assert "Missing docstring" in validated[0]

def test_keeps_legitimate_syntax_error(tmp_path):
    """Findings claiming syntax errors on actually broken files must be kept."""
    test_file = tmp_path / "broken.py"
    test_file.write_text("def fail(:") # Actual syntax error
    
    findings = ["- Syntax error in broken.py. (Source: broken.py)"]

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        # Force a PyCompileError to simulate real compiler failure
        with patch("py_compile.compile", side_effect=py_compile.PyCompileError("Syntax Error", "broken.py")):
            validated = cross_validate_syntax_findings(findings)
            assert len(validated) == 1
            assert "Syntax error" in validated[0]
