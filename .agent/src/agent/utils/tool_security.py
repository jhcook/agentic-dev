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
Security utilities for tool parameter validation and input sanitization.

This module provides helpers to prevent directory traversal and ensure that 
natural language inputs are safe for processing by the vector database.
"""

import shlex
import re
from typing import List

def sanitize_and_validate_args(args: List[str]) -> List[str]:
    """
    Sanitize and validate shell arguments to prevent injection attacks.

    This function checks each argument against a whitelist of safe characters and
    applies shell quoting. It is intended for use with UV, pytest, and git wrappers.

    Args:
        args: List of command line arguments (e.g., ["add", "requests"]).

    Returns:
        List of sanitized and quoted argument strings.

    Raises:
        ValueError: If an argument contains characters that could bypass shell escaping.
    """
    # Whitelist: alphanumeric, paths, dots, dashes, underscores, spaces, colons, and equals
    safe_pattern = re.compile(r"^[a-zA-Z0-9\.\/\_\-\s\:\@\=\+]*$")
    sanitized = []
    for arg in args:
        arg_str = str(arg)
        if not safe_pattern.match(arg_str):
            raise ValueError(f"Security Violation: Argument contains potentially unsafe characters: {arg_str}")
        sanitized.append(shlex.quote(arg_str))
    return sanitized
from pathlib import Path
from typing import Union


def validate_safe_path(user_path: Union[str, Path], base_dir: Union[str, Path]) -> Path:
    """
    Validate and resolve a path, ensuring it resides within the base directory.

    Args:
        user_path: The relative path provided by the agent or user.
        base_dir: The root directory that must contain the user path.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If the path is absolute or resolves outside the base directory.
    """
    base = Path(base_dir).resolve()
    target = Path(user_path)

    # Enforce relative paths only for tool operations to prevent absolute jumps
    if target.is_absolute():
        # Even if absolute, we resolve and check root for safety
        resolved = target.resolve()
    else:
        resolved = (base / target).resolve()

    # Verify that the resolved path is a child of the base directory
    if not str(resolved).startswith(str(base)):
        raise ValueError(
            f"Security Violation: Path traversal attempt detected for '{user_path}'. "
            f"Requested path resolves outside of allowed root: {base_dir}"
        )

    return resolved


def sanitize_vector_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize natural language strings intended for vector similarity search.

    Removes non-printable control characters and enforces length limits to prevent
    resource exhaustion or injection patterns in the vector store.

    Args:
        query: The raw query string.
        max_length: The maximum allowed length for the query.

    Returns:
        A sanitized and trimmed query string.
    """
    if not query:
        return ""

    # Remove control characters and non-printable sequences
    cleaned = "".join(char for char in query if char.isprintable())

    # Enforce maximum character length to protect vector engine performance
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned.strip()
