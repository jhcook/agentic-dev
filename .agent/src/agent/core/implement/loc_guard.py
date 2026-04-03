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

"""Gate 0: Projected LOC check for the runbook generation pipeline (INFRA-177).

Extracted from guards.py to keep that module under the 1000-line hard limit.

Design: accepts raw runbook *content* and parses NEW blocks (via
``parse_code_blocks``) and MODIFY blocks (via ``parse_search_replace_blocks``)
independently.  This matches the actual parser output schemas:

- NEW:    ``{"file": str, "content": str}``
- MODIFY: ``{"file": str, "search": str, "replace": str}``
"""

import logging
from pathlib import Path
from typing import List

from agent.core.config import config

logger = logging.getLogger(__name__)


def check_projected_loc(content: str, project_root: Path) -> List[str]:
    """Gate 0: Return correction strings for blocks that exceed config.max_file_loc.

    Parses both ``[NEW]`` blocks (full-file content) and ``[MODIFY]`` S/R
    blocks from *content* to calculate the projected line count after each
    change.  Files that would exceed the limit are returned as actionable
    correction strings for the AI.

    Runs before schema validation in ``run_generation_gates`` so the AI gets
    immediate, low-cost feedback on architectural size boundaries.

    Args:
        content: Raw runbook markdown string from the AI.
        project_root: Repository root used to resolve relative file paths.

    Returns:
        List of human-readable correction strings, one per violation.
        An empty list means all blocks are within the LOC limit.
    """
    # Local imports avoid circular dependencies at module load time.
    from agent.core.implement.parser import (  # noqa: PLC0415
        parse_code_blocks,
        parse_search_replace_blocks,
    )

    limit = getattr(config, "max_file_loc", 500)
    errors: List[str] = []

    # -----------------------------------------------------------------
    # NEW blocks: full content line count is the projected LOC.
    # -----------------------------------------------------------------
    for block in parse_code_blocks(content):
        file_path = block.get("file", "")
        if not file_path:
            continue

        block_content = block.get("content", "")
        stripped = block_content.strip("\n")
        projected_loc = stripped.count("\n") + 1 if stripped else 0
        current_loc = 0
        delta_loc = projected_loc

        if projected_loc > limit:
            _log_and_append(errors, file_path, current_loc, delta_loc, projected_loc, limit)

    # -----------------------------------------------------------------
    # MODIFY blocks: delta on the existing file's LOC.
    # -----------------------------------------------------------------
    for block in parse_search_replace_blocks(content):
        file_path = block.get("file", "")
        if not file_path:
            continue

        full_path = (project_root / file_path).resolve()
        if not full_path.exists():
            continue  # AC-4: missing target is a no-op; delegated to S/R gate

        try:
            raw = full_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "projected_loc_read_fail",
                extra={"file": file_path, "error": str(exc)},
            )
            continue

        current_loc = raw.count("\n") + (0 if raw.endswith("\n") else 1)

        search_text = block.get("search", "").strip("\n")
        replace_text = block.get("replace", "").strip("\n")
        search_lines = search_text.count("\n") + 1 if search_text else 0
        replace_lines = replace_text.count("\n") + 1 if replace_text else 0
        delta_loc = replace_lines - search_lines
        projected_loc = max(0, current_loc + delta_loc)

        if projected_loc > limit:
            _log_and_append(errors, file_path, current_loc, delta_loc, projected_loc, limit)

    return errors


def _log_and_append(
    errors: List[str],
    file_path: str,
    current_loc: int,
    delta_loc: int,
    projected_loc: int,
    limit: int,
) -> None:
    """Emit a structured warning and append a correction string."""
    logger.warning(
        "projected_loc_gate_fail",
        extra={
            "file": file_path,
            "current_loc": current_loc,
            "delta_loc": delta_loc,
            "projected_loc": projected_loc,
            "limit": limit,
        },
    )
    errors.append(
        f"File '{file_path}' would reach {projected_loc} lines after this change "
        f"(limit: {limit}). Split the change into smaller modules or use a more "
        f"targeted modification to stay within the architectural LOC boundary."
    )
