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

"""
Parity tests to ensure new search tools match legacy tool behavior.
"""

import pytest
from pathlib import Path
from agent.core.adk.tools import make_tools
from agent.tools.search import search_codebase

def test_search_parity_smoke(tmp_path: Path):
    """
    Ensures the new search tool returns similar results to the legacy one
    for a basic keyword search.
    """
    # Create test data
    test_file = tmp_path / "logic.py"
    test_file.write_text("def unique_marker_function(): pass")
    
    # Legacy tool
    legacy_search = make_tools(tmp_path)[1] # search_codebase is index 1
    legacy_result = legacy_search("unique_marker_function")
    
    # New tool
    new_result = search_codebase("unique_marker_function", tmp_path)
    
    # Both should find the marker
    assert "unique_marker_function" in legacy_result
    assert "unique_marker_function" in new_result
