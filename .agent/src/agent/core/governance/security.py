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

"""Security enforcement for AI prompts and file tree injection (ADR-027)."""

import re
from pathlib import Path
from typing import List, Set

# ADR-027: Security Blocklist for File Tree Injection
SECURITY_BLOCKLIST_PATHS = {
    ".env",
    "secrets",
    ".agent/secrets",
    ".agent/cache",
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
}

# Restricted file extensions that should never be injected into prompts
RESTRICTED_EXTENSIONS = {".pem", ".key", ".crt", ".env", ".jsonl", ".db", ".sqlite"}

def is_sensitive_path(path: Path) -> bool:
    """Check if a path or any of its parents are in the security blocklist.

    Args:
        path: The filesystem path to check.

    Returns:
        True if the path is sensitive and should be excluded from AI context.
    """
    # Check file extension first
    if path.suffix.lower() in RESTRICTED_EXTENSIONS:
        return True

    # Check path parts against blocklist
    path_parts = set(path.parts)
    if any(blocked in path_parts for blocked in SECURITY_BLOCKLIST_PATHS):
        return True
    
    # Check for substring matches for common secret patterns if parts check misses
    path_str = str(path).lower()
    if "secrets/" in path_str or "/secrets" in path_str or ".env" in path_str:
        return True

    return False

def sanitize_tree_output(tree_text: str) -> str:
    """Filter sensitive lines from a generated file tree string.

    Args:
        tree_text: Raw output from get_file_tree.

    Returns:
        Sanitized tree text with blocked paths removed.
    """
    lines = tree_text.splitlines()
    sanitized_lines = []
    
    for line in lines:
        # Simple heuristic: if any blocked keyword appears in the tree line, drop it
        if not any(blocked in line for blocked in SECURITY_BLOCKLIST_PATHS):
            sanitized_lines.append(line)
            
    return "\n".join(sanitized_lines)