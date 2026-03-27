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
from gates.docstring_validator import DocstringValidator

def test_filename_bypass_logic():
    """Verify that files matching test patterns bypass docstring requirements.
    
    Covers Scenario 1: Given a new file named test_utility.py, docstring gate 
    must be bypassed.
    """
    validator = DocstringValidator()
    
    # pytest patterns should PASS immediately
    res1 = validator.validate(Path("test_utility.py"), "def f(): pass")
    assert res1.status == "PASS"
    assert "Bypassed" in res1.message

    res2 = validator.validate(Path("utils_test.py"), "def f(): pass")
    assert res2.status == "PASS"

def test_downgrade_to_warning():
    """Verify that missing docstrings in new source files result in warnings.
    
    Covers Scenario 2: token_counter.py with missing __init__ docstring 
    should result in a warning.
    """
    validator = DocstringValidator()
    content = "def token_counter(): pass"
    result = validator.validate(Path("token_counter.py"), content)
    
    assert result.status == "WARNING"
    assert "missing function docstring" in result.message.lower()

def test_security_path_anchoring():
    """Ensure path traversal naming cannot be used to bypass the gate.
    
    Verifies that only real test files at appropriate locations are bypassed.
    """
    validator = DocstringValidator()
    # Deceptive path anchoring check
    result = validator.validate(Path("../test_auth.py"), "def secret(): pass")
    assert result.status == "WARNING"  # Treated as a regular file needing docs

def test_error_handling_graceful():
    """Verify system handles non-existent paths gracefully.
    
    Covers Scenario 4: Error handling should not attribute failures to docstrings.
    """
    validator = DocstringValidator()
    with pytest.raises(FileNotFoundError):
        validator.validate(Path("non_existent_path.py"), "")
