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

"""Post-processing passes for generated runbook content.

Split from runbook_generation.py (INFRA-145) to satisfy the 1000-LOC governance
hard limit. All public symbols are re-exported from runbook_generation.py for
backward compatibility.

These functions are pure string transformations applied after AI generation to
autocorrect common model output failures (fence imbalance, duplicate blocks, etc).
"""

import re
import logging
from typing import Dict

from rich.console import Console

from agent.core.logger import get_logger

logger = get_logger(__name__)
console = Console()


def strip_empty_sr_blocks(content: str) -> str:
    """Remove malformed S/R blocks where the SEARCH section is empty (AC-1).

    The AI occasionally generates blocks with no search text, which the
    implementation engine would otherwise interpret as 'replace empty string',
    effectively prepending the content to the start of the file.

    Only strips blocks where the text between <<<SEARCH and === contains
    no non-whitespace characters (i.e. truly empty or whitespace-only SEARCH).
    """
    def _replace_empty(m: re.Match) -> str:
        search_text = m.group(1)
        if not search_text.strip():
            return "<!-- stripped empty SEARCH block (INFRA-184) -->"
        return m.group(0)  # preserve valid blocks unchanged

    # Capture the text between <<<SEARCH\n and \n=== — non-greedy
    pattern = re.compile(r'<<<SEARCH\n(.*?)\n===\n.*?\n>>>', re.DOTALL)
    return pattern.sub(_replace_empty, content)


def _fix_changelog_sr_headings(content: str) -> str:
    """Rewrite CHANGELOG S/R SEARCH blocks to avoid MD024/MD025 violations.

    The AI consistently uses ``# Changelog`` as the SEARCH anchor, which
    is a top-level heading inside the runbook and triggers MD025 (multiple
    H1s) and MD024 (duplicate headings).  This pass rewrites the SEARCH
    side to use the first sub-heading inside the file (``## [Unreleased]``
    or its suffixed form) instead, which is equally unique but doesn't
    violate heading rules.

    Also fixes the case where the AI uses bare ``## [Unreleased]`` but
    the actual CHANGELOG.md on disk has ``## [Unreleased] (Updated by story)``
    from a prior run.
    """
    # Case 1: AI anchored on # Changelog (H1) — rewrite to ## [Unreleased]
    content = re.sub(
        r'<<<SEARCH\n# Changelog\n===\n# Changelog',
        '<<<SEARCH\n## [Unreleased]\n===\n## [Unreleased] (Updated by story)',
        content,
    )

    # Case 2: AI used bare ## [Unreleased] but file may have a suffix.
    # Read the actual line from CHANGELOG.md on disk.
    try:
        from pathlib import Path as _Path
        from agent.core.config import config as _config
        changelog_path = _config.repo_root / "CHANGELOG.md"
        if changelog_path.exists():
            for line in changelog_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("## [Unreleased]"):
                    actual_line = line.strip()
                    if actual_line != "## [Unreleased]":
                        # Replace bare SEARCH anchor with the actual line
                        content = content.replace(
                            "<<<SEARCH\n## [Unreleased]\n===",
                            f"<<<SEARCH\n{actual_line}\n===",
                        )
                    break
    except Exception:
        pass

    return content


def _ensure_blank_lines_around_fences(content: str) -> str:
    """Ensure every fenced code block is surrounded by blank lines (MD031).

    Inserts a blank line before an opening fence when the previous line
    is non-empty prose, and after a closing fence when the next line is
    non-empty.  Skips fences already correctly surrounded.
    """
    # Blank line before an opening fence if immediately preceded by text
    content = re.sub(r'([^\n])\n(```|~~~)', r'\1\n\n\2', content)
    # Blank line after a closing fence if immediately followed by text
    content = re.sub(r'(^```|^~~~)(\n)([^\n`~])', r'\1\2\n\3', content, flags=re.MULTILINE)
    return content


def _rebalance_fences(content: str) -> str:
    """Deterministically close any orphaned code fences in each Step block.

    The LLM cannot reliably balance nested fences, especially when embedding
    ``.md`` files that contain their own code examples.  Rather than trusting
    the model, this pass makes fence balance a *pipeline guarantee*.

    Strategy
    --------
    1. Split the assembled runbook on ``### Step N:`` boundaries.
    2. Within each block, walk line-by-line tracking open/close state of
       *backtick* fences and *tilde* fences independently (separate
       namespaces in CommonMark).
    3. If a block ends with an open fence, append the matching closer
       (``` or ~~~) before the next step begins.

    This is purely syntactic — no AI involved.
    """
    step_pat = re.compile(r'(?=^### Step \d+:)', re.MULTILINE)
    parts = step_pat.split(content)

    fixed_parts: list = []
    total_closers_added = 0

    backtick_fence_re = re.compile(r'^\s*(`{3,})\w*\s*$')
    tilde_fence_re = re.compile(r'^\s*(~{3,})\w*\s*$')

    for part in parts:
        backtick_open = False
        tilde_open = False

        for line in part.splitlines():
            if backtick_fence_re.match(line):
                backtick_open = not backtick_open
            elif tilde_fence_re.match(line):
                tilde_open = not tilde_open

        closers = ""
        if backtick_open:
            closers += "```\n"
            total_closers_added += 1
            logger.warning(
                "fence_rebalanced",
                extra={"type": "backtick", "block_preview": part[:80].strip()},
            )
        if tilde_open:
            closers += "~~~\n"
            total_closers_added += 1
            logger.warning(
                "fence_rebalanced",
                extra={"type": "tilde", "block_preview": part[:80].strip()},
            )
        fixed_parts.append(part + closers)

    if total_closers_added:
        console.print(
            f"[yellow]🔧 Fence rebalancer: closed {total_closers_added} "
            f"orphaned fence(s)[/yellow]"
        )

    return "".join(fixed_parts)


def _ensure_modify_blocks_fenced(content: str) -> str:
    """Wrap unfenced [MODIFY] S/R block content in code fences.

    Scans for ``#### [MODIFY] <path>`` headers and checks if the body
    between that header and the next ``####`` / ``###`` header has a
    code fence enclosing the ``<<<SEARCH`` / ``===`` / ``>>>`` markers.
    If not, wraps the bare S/R content in a fenced code block with
    language inferred from the file extension.

    This autocorrects the common AI failure where the MODIFY block is
    emitted directly after the heading without a fenced code block.
    """
    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }
    # Split on [MODIFY] headers, preserving the header line
    parts = re.split(r'(####\s+\[MODIFY\]\s+.+)', content)
    result = []
    for idx, part in enumerate(parts):
        result.append(part)
        if re.match(r'####\s+\[MODIFY\]\s+', part) and idx + 1 < len(parts):
            body = parts[idx + 1]
            has_sr = re.search(r'<<<SEARCH', body)
            has_fence = re.search(r'(?:^|\n)\s*(`{3,}|~{3,})', body)
            if has_sr and not has_fence:
                # Infer language from file extension
                path_match = re.search(r'\[MODIFY\]\s+(.+)', part)
                path = path_match.group(1).strip().strip('`') if path_match else ""
                # Strip escaped underscores for clean extension detection
                path_clean = path.replace('\\_', '_')
                ext = "." + path_clean.rsplit(".", 1)[-1] if "." in path_clean else ""
                lang = ext_lang.get(ext, "python")
                body_stripped = body.strip('\n')
                parts[idx + 1] = f"\n```{lang}\n{body_stripped}\n```\n"
                logger.warning(
                    "auto_fenced_modify_block",
                    extra={"path": path, "lang": lang},
                )
    return "".join(result)


def _dedup_modify_blocks(content: str) -> str:
    """Remove duplicate [NEW] and [MODIFY] blocks for the same file path.

    When the AI generates multiple blocks for the same file across
    different steps, only the FIRST occurrence is kept. Later occurrences
    are replaced with a cross-reference comment.

    This is a deterministic safety net for the one-file-one-block rule
    enforced via the prompt constraints.
    """
    # Track which files have been seen in any block type
    seen_files: Dict[str, tuple] = {}  # path -> (step_number, action)
    duplicates_removed = 0

    # Match NEW or MODIFY headers with their content up to next #### or ### header
    pattern = re.compile(
        r'(####\s+\[(NEW|MODIFY)\]\s+(.+?)\n)'
        r'(.*?)'
        r'(?=####\s+\[|###\s+|\Z)',
        re.DOTALL,
    )

    def _replace_duplicate(match: re.Match) -> str:
        nonlocal duplicates_removed
        action = match.group(2)
        file_path = match.group(3).strip().strip('`')

        # Extract step number from surrounding context
        step_match = re.search(
            r'### Step (\d+):.*?$',
            content[:match.start()],
            re.MULTILINE,
        )
        current_step = int(step_match.group(1)) if step_match else 0

        if file_path in seen_files:
            duplicates_removed += 1
            original_step, original_action = seen_files[file_path]
            logger.warning(
                "dedup_file_block",
                extra={
                    "file": file_path,
                    "original_step": original_step,
                    "original_action": original_action,
                    "duplicate_step": current_step,
                    "duplicate_action": action,
                },
            )
            return (
                f"<!-- DEDUP: {file_path} already [{original_action}] in Step "
                f"{original_step}. All changes for this file should be "
                f"consolidated there. -->\n\n"
            )
        else:
            seen_files[file_path] = (current_step, action)
            return match.group(0)  # Keep original

    result = pattern.sub(_replace_duplicate, content)

    if duplicates_removed > 0:
        console.print(
            f"[yellow]🔧 Dedup: Removed {duplicates_removed} duplicate "
            f"file block(s) (one-file-one-block rule)[/yellow]"
        )

    return result


def _escape_dunder_paths(content: str) -> str:
    r"""Escape double underscores in [NEW/MODIFY/DELETE] header paths.

    Markdown interprets ``__init__`` as bold (``**init**``). This pass
    finds file paths in block headers and escapes ``__`` → ``\_\_`` so
    the path renders literally.
    """
    def _escape_path(match: re.Match) -> str:
        prefix = match.group(1)  # e.g. '#### [MODIFY] '
        path = match.group(2)
        # Only escape __ that are part of Python dunder names
        escaped = path.replace('__', r'\_\_')
        return f"{prefix}{escaped}"

    return re.sub(
        r'(####\s+\[(?:NEW|MODIFY|DELETE)\]\s+)(.+)',
        _escape_path,
        content,
    )




# ---------------------------------------------------------------------------
# Path validation helpers (used by _autocorrect_schema_violations)
# ---------------------------------------------------------------------------

import re as _re_pp  # avoid shadowing module-level re

_PATH_LIKE_RE = _re_pp.compile(
    r"^(?:[\w.\-]+/[\w.\-/]+"
    r"|[\w.\-]+\.(?:py|md|yaml|yml|json|toml|sh|txt|js|ts|tsx|jsx|go|rs|java|rb|cfg|ini|env))$"
)
_PROSE_INDICATORS_RE = _re_pp.compile(
    r"[\\|()\[\]]|\bpattern\b|\bregex\b|\bcompile\b|DOTALL|re\.|\\s\+"
)


def _is_valid_path_header(raw: str) -> bool:
    """Return True if *raw* looks like a repository-relative file path."""
    candidate = raw.strip().strip("`").split()[0]
    if _PROSE_INDICATORS_RE.search(candidate):
        return False
    return bool(_PATH_LIKE_RE.match(candidate))

def _autocorrect_schema_violations(content: str) -> str:
    """Deterministic healer for common AI schema violations.

    Six fixes in order:
    1. Prose [MODIFY/NEW] headers (regex/code leaked out of a fence) → stripped.
    2. Empty [MODIFY] blocks with no <<<SEARCH → stripped.
    3. [NEW] blocks containing <<<SEARCH → SEARCH fragment removed.
    4. Oversized SEARCH blocks → trimmed to identify anchor.
    5. Empty SEARCH blocks → stripped (AC-1).
    6. Empty function-after blocks → stripped (AC-3).
    """
    # Apply AC-1 early
    content = strip_empty_sr_blocks(content)
    # ── 1. Prose op headers ──────────────────────────────────────────────────
    def _check_op_header(m: re.Match) -> str:
        raw_path = m.group(2)
        if not _is_valid_path_header(raw_path):
            logger.warning(
                "schema_autocorrect_prose_header_stripped",
                extra={"header": raw_path[:120]},
            )
            return f"<!-- schema-autocorrect: stripped prose header: {raw_path[:80]} -->"
        return m.group(0)

    content = re.sub(
        r"(?m)^(#### \[(?:MODIFY|NEW)\] )(.+?)$",
        _check_op_header,
        content,
    )

    # ── 2. Empty [MODIFY] blocks (no <<<SEARCH) ──────────────────────────────
    def _check_modify_body(m: re.Match) -> str:
        if "<<<SEARCH" not in m.group(0):
            logger.warning(
                "schema_autocorrect_empty_modify_stripped",
                extra={"snippet": m.group(0)[:80]},
            )
            # Extract path for the comment so developers can trace what was removed
            path_match = re.search(r"#### \[MODIFY\] (.+?)$", m.group(0), re.MULTILINE)
            path_hint = path_match.group(1).strip() if path_match else "unknown"
            return (
                f"<!-- schema-autocorrect: removed empty MODIFY block for "
                f"{path_hint} (no SEARCH/REPLACE content) -->\n\n"
            )
        return m.group(0)

    content = re.sub(
        r"(?ms)^#### \[MODIFY\] .+?\n(?:(?!^#{3,4}\s).)*(?=^#{3,4}\s|\Z)",
        _check_modify_body,
        content,
    )

    # ── 3. [NEW] blocks containing <<<SEARCH → strip the SEARCH fragment ─────
    def _fix_new_with_search(m: re.Match) -> str:
        if "<<<SEARCH" not in m.group(0):
            return m.group(0)
        cleaned = re.sub(
            r"<<<SEARCH.*?>>>",
            "<!-- schema-autocorrect: SEARCH removed from [NEW] block -->",
            m.group(0),
            flags=re.DOTALL,
        )
        logger.warning(
            "schema_autocorrect_new_search_stripped",
            extra={"header": m.group(0)[:80]},
        )
        return cleaned

    content = re.sub(
        r"(?ms)^#### \[NEW\] .+?\n(?:(?!^#{3,4}\s).)*(?=^#{3,4}\s|\Z)",
        _fix_new_with_search,
        content,
    )

    # ── 4. Oversized SEARCH blocks (whole-file snapshots) ──────────────────
    # When SEARCH > 100 lines, the fuzzy corrector hits O(n²) overhead and
    # similarity scores drop below threshold because the file has evolved.
    # Re-anchor: find a minimal verbatim prefix from the actual file that
    # uniquely identifies the insertion point (first 15 matching lines).
    _SEARCH_DELIM = re.compile(r"<<<SEARCH\n(.*?)\n===\n", re.DOTALL)
    _BLOCK_PATH_RE = re.compile(r"#### \[MODIFY\] ([^\n]+)\n")
    _ANCHOR_LINES = 15
    _SEARCH_MAX_LINES = 100

    def _trim_oversized_search(block_text: str, file_path_str: str) -> str:
        def _replacer(m: re.Match) -> str:
            search_text = m.group(1)
            n_search = len(search_text.splitlines())
            if n_search <= _SEARCH_MAX_LINES:
                return m.group(0)  # within budget — leave untouched

            # Resolve file
            from agent.core.implement.resolver import resolve_path  # noqa: PLC0415
            abs_path = resolve_path(file_path_str)
            if abs_path is None or not abs_path.exists():
                return m.group(0)  # NEW or missing — can't trim

            file_lines = abs_path.read_text().splitlines()
            search_lines = [l.strip() for l in search_text.splitlines()]

            # Find the window in the file that best starts the SEARCH
            best_offset = -1
            for off in range(max(1, len(file_lines) - _ANCHOR_LINES + 1)):
                if [l.strip() for l in file_lines[off : off + _ANCHOR_LINES]] == search_lines[:_ANCHOR_LINES]:
                    best_offset = off
                    break

            if best_offset < 0:
                # Couldn't find exact anchor lines — fall back to actual file head
                best_offset = 0

            anchor = "\n".join(file_lines[best_offset : best_offset + _ANCHOR_LINES])
            logger.warning(
                "schema_autocorrect_oversized_search_trimmed",
                extra={"file": file_path_str, "original_lines": n_search, "anchor_lines": _ANCHOR_LINES},
            )
            # Keep the === and the rest of the replace delimiter intact
            return f"<<<SEARCH\n{anchor}\n===\n"

        return _SEARCH_DELIM.sub(_replacer, block_text)

    # Apply per [MODIFY] block
    def _process_modify_block(m: re.Match) -> str:
        path_match = _BLOCK_PATH_RE.search(m.group(0))
        if not path_match:
            return m.group(0)
        return _trim_oversized_search(m.group(0), path_match.group(1).strip())

    content = re.sub(
        r"(?ms)^#### \[MODIFY\] .+?\n(?:(?!^#{3,4}\s).)*(?=^#{3,4}\s|\Z)",
        _process_modify_block,
        content,
    )

    # ── 6. Empty function-after blocks (AC-3) ────────────────────────────────
    # Failure Mode 2: schema rejects empty function-after.blocks lists.
    # We strip these to satisfy validation constraints.
    content = re.sub(
        r'"function-after":\s*\{\s*"blocks":\s*\[\s*\]\s*\},?',
        '/* schema-autocorrect: stripped empty function-after blocks */',
        content
    )

    return content


def _normalize_list_markers(content: str) -> str:
    """Normalise bullet and ordered-list markers to satisfy MD004/MD030.

    Converts ``*   item`` (asterisk + 3 spaces) to ``- item`` (dash +
    1 space) and ``N.  item`` (2+ spaces after period) to ``N. item``
    (1 space).  Only operates on lines that are clearly list items
    (outside of fenced code blocks).
    """
    lines = content.splitlines(keepends=True)
    in_fence = False
    result = []
    for line in lines:
        # Track fence state so we don't mangle code inside blocks
        stripped = line.lstrip()
        if re.match(r'^(`{3,}|~{3,})\S*\s*$', stripped):
            in_fence = not in_fence
        if not in_fence:
            # MD004: asterisk bullet → dash
            line = re.sub(r'^(\s*)\*( {2,})', lambda m: m.group(1) + '- ', line)
            # MD030: multiple spaces after ordered-list period
            line = re.sub(r'^(\s*\d+\.)(\s{2,})', lambda m: m.group(1) + ' ', line)
        result.append(line)
    return "".join(result)

