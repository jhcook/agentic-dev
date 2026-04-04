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

"""Block assembly helpers for the chunked runbook generation pipeline.

Split from runbook_generation.py (INFRA-145) to satisfy the 1000-LOC governance
hard limit. All public symbols are re-exported from runbook_generation.py for
backward compatibility.
"""

import re
import logging
from typing import Dict, List, Optional

from agent.core.logger import get_logger

logger = get_logger(__name__)


def _derive_search_from_file(
    replace: str,
    file_path: str,
    modify_contents: Optional[Dict[str, str]],
) -> Optional[str]:
    """Derive a verbatim SEARCH block from the actual file using the replace as a guide.

    Discards the AI's (potentially hallucinated) search text and instead finds
    the lines in the actual file that the replace block is targeting, using a
    longest-common-subsequence alignment between the replace text and the file.

    The common lines (lines that exist in both the file and the replace) mark
    the region being modified.  We return the actual file lines spanning that
    region as the verbatim SEARCH anchor.

    Args:
        replace: The AI-generated replacement text (new content).
        file_path: Repo-relative path used to look up actual content.
        modify_contents: Pre-loaded {path: file_content} dict.

    Returns:
        Verbatim lines from the actual file to use as SEARCH, or None if
        the file is not available or no common region can be found.
    """
    import difflib

    if not modify_contents or not replace.strip():
        return None

    actual = modify_contents.get(file_path) or modify_contents.get(
        file_path.lstrip(".")
    )
    if not actual:
        return None

    replace_lines = replace.splitlines()
    actual_lines = actual.splitlines()

    # Align replace against the actual file using LCS.
    # Matching blocks = lines that exist verbatim in both.
    matcher = difflib.SequenceMatcher(None, actual_lines, replace_lines, autojunk=False)
    blocks = matcher.get_matching_blocks()  # last block is always the sentinel (0,0,0)

    # Real blocks (excluding sentinel)
    real_blocks = [(a, b, size) for a, b, size in blocks if size > 0]
    if not real_blocks:
        return None  # no common lines — can't derive anchor

    # The SEARCH spans from the first to last matched region in the actual file.
    actual_start = real_blocks[0][0]
    actual_end = real_blocks[-1][0] + real_blocks[-1][2]

    search_lines = actual_lines[actual_start:actual_end]
    if not search_lines:
        return None

    derived = "\n".join(search_lines)
    logger.debug(
        "search_derived_from_file",
        extra={
            "file": file_path,
            "search_lines": len(search_lines),
            "first_line": search_lines[0][:80],
        },
    )
    return derived



def _assemble_block_from_json(
    block: "GenerationBlock",
    modify_contents: Optional[Dict[str, str]] = None,
) -> str:
    """Convert structured JSON ops into markdown with injected delimiters.

    This is the core of INFRA-181: the LLM never writes ``<<<SEARCH``,
    ``===``, ``>>>``, or ``#### [NEW/MODIFY/DELETE]`` — Python does.
    If the block has no ops (legacy ``content`` field), returns content as-is.

    Args:
        block: The parsed generation block with ops.
        modify_contents: Pre-loaded actual file contents keyed by repo-relative
            path.  When provided, MODIFY search strings are validated and
            re-anchored against the real file to eliminate hallucinations.
    """
    if not block.ops:
        return block.content

    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }

    parts: List[str] = []
    for op in block.ops:
        action = str(op.get("op", "modify")).upper()
        path = op.get("file", "unknown")
        parts.append(f"#### [{action}] {path}")
        parts.append("")  # blank line after header

        if action == "NEW":
            content = op.get("content", "")
            # Infer language from file extension for syntax highlighting
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            lang = ext_lang.get(ext, "")
            parts.append(f"```{lang}")
            parts.append(content)
            parts.append("```")

        elif action == "MODIFY":
            replace = op.get("replace", "")
            # Derive the SEARCH verbatim from the real file using the replace
            # as an LCS anchor. The AI never generates a `search` field —
            # it wastes tokens and is always hallucinated.
            search = _derive_search_from_file(replace, path, modify_contents)
            if search is None:
                # File not in modify_contents (e.g. new file, or outside repo).
                # Fall back to whatever the AI provided, if anything.
                search = op.get("search", "")
            parts.append("```")
            parts.append("<<<SEARCH")
            parts.append(search)
            parts.append("===")
            parts.append(replace)
            parts.append(">>>")
            parts.append("```")

        elif action == "DELETE":
            rationale = op.get("rationale", "File no longer needed.")
            parts.append(f"Rationale: {rationale}")

        parts.append("")  # blank line between ops

    return "\n".join(parts).strip()



def _ensure_new_blocks_fenced(content: str) -> str:
    """Wrap unfenced [NEW] block content in code fences.

    Scans for ``#### [NEW] <path>`` headers and checks if the content
    between that header and the next ``####`` / ``###`` header is fenced.
    If not, wraps it in a fenced code block with language inferred from
    the file extension.

    Always uses backtick fences (MD048). The inner content of .md files
    is written by the AI and typically does not contain triple-backtick
    code blocks — and when it does, the fence rebalancer closes any
    orphaned fences deterministically.
    """
    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }
    # Split on [NEW] headers, preserving the header
    parts = re.split(r'(####\s+\[NEW\]\s+.+)', content)
    result = []
    for idx, part in enumerate(parts):
        result.append(part)
        # Check if this is a [NEW] header and the NEXT part is content
        if re.match(r'####\s+\[NEW\]\s+', part) and idx + 1 < len(parts):
            body = parts[idx + 1]
            # Check if body already contains a code fence
            if not re.search(r'(?:^|\n)\s*(`{3,}|~{3,})', body):
                # Extract path for language detection
                path_match = re.search(r'\[NEW\]\s+(.+)', part)
                path = path_match.group(1).strip().strip('`') if path_match else ""
                ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
                lang = ext_lang.get(ext, "")
                body_stripped = body.strip('\n')
                parts[idx + 1] = f"\n```{lang}\n{body_stripped}\n```\n"
    return "".join(result)

