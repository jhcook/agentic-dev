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
Unit tests for the search tool module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.tools.search import find_symbol, find_references

def test_find_symbol_nested(tmp_path: Path) -> None:
    """
    Verifies that find_symbol correctly identifies nested classes and methods.
    """
    # Create a dummy Python file with nested constructs
    py_file = tmp_path / "nested_code.py"
    py_file.write_text("""
class OuterClass:
    class InnerClass:
        def nested_method(self):
            pass

def top_level_func():
    pass
""")

    # Mock subprocess.run to simulate Ripgrep finding the file
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=str(py_file), returncode=0)

        # Verify top-level function
        res = find_symbol("top_level_func", tmp_path)
        assert "nested_code.py:7 (function definition)" in res

        # Verify nested class
        res = find_symbol("InnerClass", tmp_path)
        assert "nested_code.py:3 (class definition)" in res

        # Verify nested method
        res = find_symbol("nested_method", tmp_path)
        assert "nested_code.py:4 (function definition)" in res

def test_find_symbol_negative_txt(tmp_path: Path) -> None:
    """
    Verifies that find_symbol returns an error for non-Python files.
    """
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("def dummy_func(): pass")

    with patch("subprocess.run") as mock_run:
        # Ripgrep might find the string in the txt file
        mock_run.return_value = MagicMock(stdout=str(txt_file), returncode=0)
        res = find_symbol("dummy_func", tmp_path)
        
        # The implementation specifically filters for .py extension
        assert "not found in Python files" in res

def test_round_trip_integration(tmp_path: Path) -> None:
    """
    Integration test for finding a symbol and then searching for its references.
    """
    app_file = tmp_path / "app.py"
    app_file.write_text("""
def process_data(data):
    return data.upper()

val = process_data("hello")
""")

    with patch("subprocess.run") as mock_run:
        def side_effect(args, **kwargs):
            if "-l" in args: # find_symbol candidate search
                return MagicMock(stdout=str(app_file), returncode=0)
            else: # find_references search
                return MagicMock(
                    stdout=f"{app_file}:5:val = process_data(\"hello\")", 
                    returncode=0
                )

        mock_run.side_effect = side_effect

        # Step 1: Find the definition
        def_res = find_symbol("process_data", tmp_path)
        assert "app.py:2" in def_res

        # Step 2: Use the name from the definition to find references
        ref_res = find_references("process_data", tmp_path)
        assert "app.py:5" in ref_res
