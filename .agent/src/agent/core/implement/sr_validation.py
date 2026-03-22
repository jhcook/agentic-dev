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

"""Post-generation S/R validation and fuzzy-match correction (INFRA-168).

Extracted from guards.py to keep that module under the 1000 LOC hard limit.
Provides:
  - validate_and_correct_sr_blocks: validates SEARCH text against actual files
  - _fuzzy_find_and_replace: runtime fuzzy match fallback for apply_search_replace
"""

import difflib
import logging
import re as _re
from pathlib import Path
from typing import Optional

from rich.console import Console

_console = Console()


def validate_and_correct_sr_blocks(
    runbook_content: str,
    repo_root: Optional[Path] = None,
    threshold: float = 0.6,
) -> tuple[str, int, int]:
    """Validate S/R SEARCH blocks against actual file content and auto-correct.

    After AI generates a runbook, this function reads each [MODIFY] target
    file from disk and verifies that every <<<SEARCH block matches actual
    content.  If a SEARCH block is hallucinated (not found in the file),
    it uses fuzzy matching to find the best matching region and rewrites
    the SEARCH text to the verified content.

    Args:
        runbook_content: Raw runbook markdown string.
        repo_root: Project root directory. Defaults to cwd.
        threshold: Minimum fuzzy similarity to auto-correct (0.0–1.0).

    Returns:
        Tuple of (corrected_content, total_blocks, corrected_count).
    """
    if repo_root is None:
        repo_root = Path.cwd()

    # Parse file sections - same regex as parser.py
    file_sections = _re.split(
        r'(?:^|\n)(?:(?:File|Modify):\s*|####\s*\[(?:MODIFY|NEW)\]\s*)`?([^\n`]+?)`?\s*\n',
        runbook_content, flags=_re.IGNORECASE,
    )

    total_blocks = 0
    corrected_count = 0
    corrected_content = runbook_content

    for i in range(1, len(file_sections), 2):
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""

        # Resolve file path
        resolved = repo_root / filepath
        if not resolved.exists():
            continue  # NEW file — nothing to validate against

        actual_content = resolved.read_text()

        # Find all S/R blocks in this section
        for match in _re.finditer(
            r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', body, _re.DOTALL
        ):
            total_blocks += 1
            search_text = match.group(1)
            replace_text = match.group(2)

            if search_text in actual_content:
                continue  # exact match — no correction needed

            # Fuzzy match: find best matching region
            search_lines = search_text.splitlines(keepends=True)
            actual_lines = actual_content.splitlines(keepends=True)
            window_size = len(search_lines)

            if window_size == 0 or len(actual_lines) == 0:
                continue

            best_ratio = 0.0
            best_start = -1

            for start in range(max(1, len(actual_lines) - window_size + 1)):
                end = min(start + window_size, len(actual_lines))
                candidate = "".join(actual_lines[start:end])
                ratio = difflib.SequenceMatcher(
                    None, candidate, search_text
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_start = start

            if best_ratio >= threshold and best_start >= 0:
                best_end = min(best_start + window_size, len(actual_lines))
                correct_text = "".join(actual_lines[best_start:best_end])
                # Strip trailing newline that splitlines(keepends=True) adds
                if correct_text.endswith("\n"):
                    correct_text = correct_text[:-1]

                # Replace the hallucinated SEARCH with verified content
                old_block = f"<<<SEARCH\n{search_text}\n===\n{replace_text}\n>>>"
                new_block = f"<<<SEARCH\n{correct_text}\n===\n{replace_text}\n>>>"
                corrected_content = corrected_content.replace(old_block, new_block, 1)
                corrected_count += 1

                _console.print(
                    f"[yellow]🔧 Auto-corrected S/R in {filepath} "
                    f"(similarity: {best_ratio:.0%})[/yellow]"
                )
                logging.info(
                    "sr_validation_corrected",
                    extra={"file": filepath, "similarity": round(best_ratio, 2)},
                )
            else:
                _console.print(
                    f"[red]⚠ Cannot auto-correct S/R in {filepath} "
                    f"(best match: {best_ratio:.0%} < {threshold:.0%} threshold)[/red]"
                )
                logging.warning(
                    "sr_validation_unfixable",
                    extra={"file": filepath, "best_ratio": round(best_ratio, 2)},
                )

    return corrected_content, total_blocks, corrected_count


def fuzzy_find_and_replace(
    content: str,
    search: str,
    replace: str,
    filepath: str,
    block_num: int,
    total_blocks: int,
    threshold: float = 0.6,
) -> Optional[str]:
    """Find the best fuzzy match for search text in content and apply replacement.

    Uses a sliding window of lines sized to the search block to find the
    highest-similarity contiguous region.  If similarity >= threshold,
    replaces that region with the replace text.

    Args:
        content: The full file content to search in.
        search: The search text to match (may not match exactly).
        replace: The replacement text.
        filepath: File path for logging.
        block_num: Block number for logging.
        total_blocks: Total blocks for logging.
        threshold: Minimum similarity ratio (0.0–1.0).

    Returns:
        The modified content if a fuzzy match was applied, None otherwise.
    """
    search_lines = search.splitlines(keepends=True)
    content_lines = content.splitlines(keepends=True)
    window_size = len(search_lines)

    if window_size == 0 or len(content_lines) == 0:
        return None

    best_ratio = 0.0
    best_start = -1

    # Slide window across all possible positions
    for start in range(max(1, len(content_lines) - window_size + 1)):
        end = min(start + window_size, len(content_lines))
        candidate = content_lines[start:end]
        ratio = difflib.SequenceMatcher(
            None, "".join(candidate), search
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = start

    if best_ratio >= threshold and best_start >= 0:
        best_end = min(best_start + window_size, len(content_lines))
        matched_text = "".join(content_lines[best_start:best_end])
        _console.print(
            f"[yellow]🔍 Fuzzy matched block {block_num}/{total_blocks} in {filepath} "
            f"(similarity: {best_ratio:.0%})[/yellow]"
        )
        logging.info(
            "search_replace_fuzzy_match",
            extra={"file": filepath, "block": f"{block_num}/{total_blocks}", "similarity": round(best_ratio, 2)},
        )
        return content.replace(matched_text, replace, 1)

    logging.warning(
        "search_replace_fuzzy_no_match",
        extra={"file": filepath, "block": f"{block_num}/{total_blocks}", "best_ratio": round(best_ratio, 2), "threshold": threshold},
    )
    return None
