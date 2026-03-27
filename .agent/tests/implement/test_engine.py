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
from implement.engine import ImplementationEngine

def test_engine_summary_logic() -> None:
    """Verify implement summary banner distinguishes between SUCCESS and WARNINGS.
    
    Covers Scenario 3: Banner only triggers INCOMPLETE for critical failures.
    """
    engine = ImplementationEngine()
    
    # Case 1: Success with warnings
    engine.results = {
        "test_auth.py": "PASS",
        "utils.py": "WARNING"
    }
    assert engine.get_verdict() == "SUCCESS WITH WARNINGS"
    assert len(engine.rejected_files) == 0

    # Case 2: Critical implementation failure
    engine.results = {
        "broken_file.py": "FAIL"
    }
    assert engine.get_verdict() == "INCOMPLETE IMPLEMENTATION"
    assert "broken_file.py" in engine.rejected_files

def test_regression_syntax_errors() -> None:
    """Ensure syntax errors in new files still trigger hard rejections."""
    engine = ImplementationEngine()
    # Assume a mock validator returns FAIL for syntax errors
    engine.results = {"invalid.py": "FAIL"}
    assert engine.get_verdict() == "INCOMPLETE IMPLEMENTATION"
