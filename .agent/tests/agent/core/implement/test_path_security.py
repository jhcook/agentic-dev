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
Unit tests for secure path anchoring and exclusion logic.
"""
import pytest
from agent.utils.path_security import is_test_file_secure

def test_strict_anchoring_resolution():
    """Verify that deceptive traversal paths do not bypass docstring gates."""
    # Deceptive path targeting auth.py via a test directory segment
    # The resolved basename is 'auth.py', which should NOT match 'test_*'
    assert is_test_file_secure("src/tests/../auth.py") is False
    
    # Path with deep traversal targeting a config file
    assert is_test_file_secure("src/test_utils/../../config/secrets.py") is False
    
    # Standard filenames
    assert is_test_file_secure("test_auth.py") is True
    assert is_test_file_secure("auth.py") is False

def test_standard_pattern_coverage():
    """Verify all standard test naming conventions from Rule 000 are covered."""
    # Python / Pytest
    assert is_test_file_secure("test_utility.py") is True
    assert is_test_file_secure("utils_test.py") is True
    
    # JS / TS / Web
    assert is_test_file_secure("Button.test.tsx") is True
    assert is_test_file_secure("api.spec.ts") is True
    
    # INFRA-173 Specific: __init__ files
    assert is_test_file_secure("__init__.py") is True
    assert is_test_file_secure("agent/core/__init__.py") is True

def test_case_insensitivity():
    """Verify that naming checks are case-insensitive for platform compatibility."""
    assert is_test_file_secure("TEST_UTILITY.PY") is True
    assert is_test_file_secure("Test_Component.Spec.JS") is True

def test_edge_cases():
    """Verify handling of empty, null, or malformed inputs."""
    assert is_test_file_secure("") is False
    assert is_test_file_secure(None) is False
    assert is_test_file_secure(".") is False
    assert is_test_file_secure("..") is False
