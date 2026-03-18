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
Shared utility helpers for agentic tools.

Provides security-critical helpers (e.g. path validation) that must behave
identically across all domain tool modules.
"""

from pathlib import Path


def validate_path(path: str, repo_root: Path) -> Path:
    """
    Validates that a path is within the repository root.

    Paths are resolved *relative to the repo root* via ``(repo_root /
    path).resolve()`` so that a bare relative path such as ``"foo/bar"`` is
    treated as ``<repo_root>/foo/bar`` rather than relative to the process
    working directory.  This prevents a class of sandbox-escape vulnerabilities
    that arise when ``Path(path).resolve()`` is used instead.

    Args:
        path: The path to validate (may be absolute or relative).
        repo_root: The absolute path to the repository root.

    Returns:
        The resolved, sandbox-safe :class:`pathlib.Path` object.

    Raises:
        ValueError: If the resolved path is outside the repository root.
    """
    resolved = (repo_root / path).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Path '{path}' is outside the repository root.")
    return resolved
