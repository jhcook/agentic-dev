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

"""Shared path validation utilities used by both core and commands layers.

Keeping this in ``agent.utils`` allows the ``core`` package to import it without
creating an architectural dependency on the ``commands`` layer.
"""
from pathlib import Path


def validate_path_integrity(target_path: str, root_dir: Path) -> bool:
    """Verify that `target_path` stays within `root_dir` after resolution.

    Prevents path-traversal attacks during generation-time file reads.
    The function is intentionally dependency-free so it can be imported
    from any layer without creating circular imports.

    Args:
        target_path: The path string to validate (may be absolute or relative).
        root_dir: The project root to confine access to.

    Returns:
        True if the resolved path is inside `root_dir`; False otherwise.
    """
    try:
        resolved_root = root_dir.resolve()
        resolved_target = (root_dir / target_path).resolve()
        return str(resolved_target).startswith(str(resolved_root))
    except (ValueError, RuntimeError):
        return False
