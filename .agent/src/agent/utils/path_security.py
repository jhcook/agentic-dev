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
Security utility for strict path anchoring and normalization in implementation gates.
"""
import os
import fnmatch

def is_test_file_secure(path: str) -> bool:
    """
    Determines if a file path refers to an excluded file (test or init) using strict anchoring.

    Normalizes the path to resolve traversal segments (..) and matches only the 
    filename against standard patterns. This prevents deceptive naming bypasses
    where a path might contain a pattern-matching string in its directory structure
    but target a non-test file.

    Args:
        path (str): The workspace-relative path to the file.

    Returns:
        bool: True if the file should be excluded from strict docstring gates.
    """
    if not path:
        return False

    # Normalize the path to resolve any traversal (..) or redundant segments
    # os.path.normpath resolves 'src/test/../auth.py' to 'src/auth.py'
    normalized = os.path.normpath(str(path)).replace("\\", "/")
    
    # Extract the filename component (the anchor)
    # Deceptive paths like '../test_auth.py' will resolve to their basename
    filename = os.path.basename(normalized)

    # Exclusion patterns based on Rule 000 and INFRA-173 requirements.
    # These cover Python (pytest), JavaScript/TypeScript (jest/mocha), and other standards.
    patterns = [
        "test_*",      # pytest/jest prefix
        "*_test.*",    # pytest/go suffix
        "*.test.*",    # modern JS/TS convention
        "*.spec.*",    # modern JS/TS convention
        "__init__.*"   # INFRA-173: exclude init files from docstring gate
    ]

    # Perform case-insensitive matching for robustness across platforms
    filename_lower = filename.lower()
    return any(fnmatch.fnmatch(filename_lower, pattern.lower()) for pattern in patterns)
