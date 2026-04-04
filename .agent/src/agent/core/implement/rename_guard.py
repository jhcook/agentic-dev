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

"""INFRA-179: Public symbol rename detection guard.

Detects when a [MODIFY] block renames or removes a public class or function
without updating all consumers in the codebase within the same runbook.
"""

import ast
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Set

from agent.core.governance import log_governance_event
from agent.core.logger import get_logger

logger = get_logger(__name__)


def _extract_public_symbols(code: str) -> Set[str]:
    """Extract public classes and functions from code using AST parsing."""
    try:
        tree = ast.parse(code)
        symbols = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if not node.name.startswith("_"):
                    symbols.add(node.name)
        return symbols
    except Exception:
        return set()


def check_api_surface_renames(
    blocks: List[Dict[str, str]], repo_root: Path
) -> List[str]:
    """Detect renames or removals of public symbols in [MODIFY] blocks.

    Ensures all consumers in the codebase are updated within the same runbook.

    Args:
        blocks: List of parsed S/R blocks with keys ``file``, ``search``,
            ``replace``.
        repo_root: Absolute path to the repository root used as the ``cwd``
            for ``grep`` searches.

    Returns:
        A list of human-readable error strings, one per orphaned consumer.
        Empty list means the gate passed.
    """
    all_renames: Dict[str, str] = {}
    all_deletions: Set[str] = set()
    file_to_removed_symbols: Dict[str, Set[str]] = {}

    # Pass 1: Identify all renames/removals across all blocks
    for block in blocks:
        filename = block.get("file", "")
        search_code = block.get("search", "")
        replace_code = block.get("replace", "")

        search_symbols = _extract_public_symbols(search_code)
        replace_symbols = _extract_public_symbols(replace_code)

        removed = search_symbols - replace_symbols
        added = replace_symbols - search_symbols

        # 1-to-1 change in a block is treated as a rename
        if len(removed) == 1 and len(added) == 1:
            old = list(removed)[0]
            new = list(added)[0]
            all_renames[old] = new
        else:
            all_deletions.update(removed)

        if removed:
            file_to_removed_symbols.setdefault(filename, set()).update(removed)

    errors: List[str] = []
    updated_files = {block["file"] for block in blocks}

    # Pass 2: Check for survivors (consumers not updated)
    for source_file, symbols in file_to_removed_symbols.items():
        for symbol in symbols:
            new_name = all_renames.get(symbol)
            pattern = rf"\b{re.escape(symbol)}\b"

            # Grep restricted to src/ and tests/ — list-based args prevent injection
            cmd = [
                "grep", "-r", "-l", "--include=*.py",
                "--exclude-dir=.venv", "--exclude-dir=__pycache__",
                pattern, "src", "tests",
            ]
            try:
                result = subprocess.run(
                    cmd, cwd=repo_root, capture_output=True, text=True, check=False
                )
                if result.returncode > 1:  # grep returns 2 on true error
                    continue

                consumers = [
                    f for f in result.stdout.splitlines()
                    if not f.endswith(source_file)
                ]
                if not consumers:
                    continue

                # Check if each consumer is covered by another block in this runbook
                orphaned = []
                for consumer in consumers:
                    is_handled = False
                    if consumer in updated_files:
                        for b in blocks:
                            if b["file"] == consumer:
                                if not re.search(pattern, b.get("replace", "")):
                                    is_handled = True
                                    break
                    if not is_handled:
                        orphaned.append(consumer)

                if orphaned:
                    status = f"renamed to '{new_name}'" if new_name else "removed"
                    msg = (
                        f"Public symbol '{symbol}' was {status} in {source_file}, "
                        f"but has live consumers in: {', '.join(orphaned)}"
                    )
                    errors.append(msg)
                    log_governance_event(
                        "api_rename_gate_fail",
                        {
                            "symbol": symbol,
                            "old_name": symbol,
                            "new_name": new_name,
                            "consumers": orphaned,
                        },
                    )
            except Exception as e:
                logger.error(f"Rename check failed for {symbol}: {e}")

    return errors
