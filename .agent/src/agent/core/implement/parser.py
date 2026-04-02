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

"""Parser utilities for AI markdown and runbooks."""

import ast
import contextlib
import os
import re
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, TypedDict, Union, Optional

import mistune

from pydantic import ValidationError

from agent.core.logger import get_logger

from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    ParsingError,
    RunbookSchema,
    RunbookStep,
    SearchReplaceBlock,
)
from agent.core.implement.chunk_models import RunbookBlock, RunbookSkeleton

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None
_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Typed structures returned by the AST parser
# ---------------------------------------------------------------------------

class RunbookOperationDict(TypedDict, total=False):
    """A single [MODIFY], [NEW], or [DELETE] operation parsed from a runbook step."""

    path: str
    """Repo-relative file path declared in the operation header."""
    blocks: List[Dict[str, str]]
    """For MODIFY — list of {'search': str, 'replace': str} pairs."""
    content: str
    """For NEW — full file content to write."""
    rationale: str
    """For DELETE — human-readable reason for deletion."""
    malformed: bool
    """True when the operation header is present but its body is invalid."""


class RunbookStepDict(TypedDict):
    """A structured implementation step from a runbook's ## Implementation Steps section."""

    title: str
    """Step title with the 'Step N: ' prefix stripped."""
    operations: List[RunbookOperationDict]
    """Ordered list of file operations belonging to this step."""


class InvalidTemplateError(Exception):
    """Raised when a runbook skeleton is malformed or lacks addressable blocks."""
    pass



def validate_path_safety(path_str: str) -> str:
    """Verify that a path does not attempt directory traversal.

    Args:
        path_str: The file path to validate.

    Returns:
        The validated path string.

    Raises:
        ParsingError: If the path is absolute or attempts to climb up (..).
    """
    if not path_str:
        return ""
    if ".." in path_str or path_str.startswith("/") or ":" in path_str:
        raise ParsingError(f"Security Violation: Potential directory traversal in path: {path_str}")
    return path_str


def validate_block_id(block_id: str) -> str:
    """Sanitize and validate a block identifier.

    Args:
        block_id: The raw identifier extracted from the template.

    Returns:
        The sanitized identifier.

    Raises:
        ParsingError: If the ID contains illegal characters or exceeds length limits.
    """
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", block_id):
        raise ParsingError(f"Security Violation: Invalid characters in block ID: {block_id}")
    if len(block_id) > 64:
        raise ParsingError(f"Security Violation: Block ID too long: {block_id[:10]}...")
    return block_id


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Filter block metadata to prevent injection and ensure storage safety."""
    sanitized = {}
    for k, v in metadata.items():
        safe_key = re.sub(r"[^a-z0-9_]", "", str(k).lower())
        if not safe_key:
            continue
        if isinstance(v, (str, int, float, bool)):
            sanitized[safe_key] = v
    return sanitized


def _unescape_path(path: str) -> str:
    """Remove markdown escapes and styling from file paths.

    Strip markers and remove backslash escapes.

    Args:
        path: Raw path string from markdown header.

    Returns:
        Clean, technical file path.
    """
    if not path:
        return ""
    # Remove bold/italic and backticks from the edges only
    path = path.strip().strip('`')
    # Strip bold (**) or (__) from the entire path string
    path = re.sub(r'^\*\*(.*?)\*\*$', r'\1', path)
    path = re.sub(r'^__(.*?)__$', r'\1', path)
    # Strip italic (*) or (_) from the entire path string
    path = re.sub(r'^\*(.*?)\*$', r'\1', path)
    path = re.sub(r'^_(.*?)_$', r'\1', path)
    # Mistune sometimes translates __ into ** or vice versa when dealing with dunder init
    # We must only restore dunder if it was converted into ** natively inside the string, but
    # it's usually better to just rely on the strict matching.
    path = re.sub(r'\*\*', '__', path)
    # Remove backslash escapes for markdown characters: _ * [ ] ( ) # + - . !
    clean_path = re.sub(r'\\([_*[\]()#+\-.!])', r'\1', path)
    return validate_path_safety(clean_path)

def parse_skeleton(content: str) -> RunbookSkeleton:
    """Parse a runbook skeleton containing @block tags into a RunbookSkeleton model.

    This function identifies block boundaries, extracts IDs and metadata, and 
    captures whitespace for exact reconstruction.

    Args:
        content: The raw string content of the skeleton file.

    Returns:
        A populated RunbookSkeleton instance.

    Raises:
        InvalidTemplateError: If tags are unbalanced or IDs are duplicated.
    """
    # Implementation logic for @block parsing goes here (defined in prior steps)
    pass

def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """Parse full-file code blocks from AI-generated markdown.

    Recognises two formats::

        ```python:path/to/file.py
        code
        ```

        File: path/to/file.py
        ```python
        code
        ```

    Content is returned **as captured** (raw bytes between the fences) without
    any trailing-newline normalisation.  This preserves the AI's output so that
    the ``validate_code_block`` gate can correctly detect a missing trailing
    newline and trigger the self-healing loop (AC-1).

    A trailing newline is present in the captured content only when the AI
    includes a blank line before the closing fence::

        ```python
        def foo():\n            pass        ← last line of code
                                 ← blank line (\\n) → captured content ends with \\n
        ```

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'`` and ``'content'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    # Pattern 1: ```lang:path format
    # Uses (?P=fence) to ensure balanced detection (e.g. 4 backticks wrap 3)
    p1 = r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]+:([\w/\.\-_]+)\n(.*?)\n\1(?P=fence)[ \t]*$'
    for match in re.finditer(p1, content, re.DOTALL):
        blocks.append({"file": _unescape_path(match.group(3)), "content": match.group(4)})

    # [NEW] only — [MODIFY] blocks are handled exclusively by parse_search_replace_blocks.
    # Pattern 2: Header followed by ``` code block
    p2 = (
        r'(?m)(?:(?:File|Create):\s*|####\s*\[(?:NEW|ADD)\]\s*)`?([^\n`]+?)`?\s*\n'
        r'( {0,3})(?P<fence2>`{3,}|~{3,})[\w]*\n(.*?)\n\2(?P=fence2)[ \t]*$'
    )
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = _unescape_path(match.group(1))
        block_content = match.group(4)
        # Skip no-op placeholder blocks (e.g. runbook uses S/R inside a [NEW] header
        # for idempotency — the real work is done by parse_search_replace_blocks).
        if block_content.startswith("<<<SEARCH"):
            continue
        if not any(b["file"] == fp for b in blocks):
            blocks.append({"file": fp, "content": block_content})
    return blocks


def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]:
    """Parse search/replace blocks from AI-generated content.

    Expected format per file::

        File: path/to/file.py
        <<<SEARCH
        exact lines
        ===
        replacement lines
        >>>

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'``, ``'search'``, ``'replace'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    # Accept [MODIFY] and [NEW] headers — [NEW] with S/R blocks inside is valid
    # for idempotent creation (file may already exist from a prior partial run).
    file_sections = re.split(
        r'(?:^|\n)(?:(?:File|Modify):\s*|####\s*\[(?:MODIFY|NEW)\]\s*)`?([^\n`]+?)`?\s*\n',
        content, flags=re.IGNORECASE,
    )
    for i in range(1, len(file_sections), 2):
        filepath = _unescape_path(file_sections[i].strip())
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        for match in re.finditer(r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', body, re.DOTALL):
            blocks.append({"file": filepath, "search": match.group(1), "replace": match.group(2)})
    if _tracer:
        span = _tracer.start_span("implement.parse_search_replace")
        span.set_attribute("block_count", len(blocks))
        span.end()
    return blocks


def extract_modify_files(runbook_content: str) -> List[str]:
    """Scan a runbook for [MODIFY] markers and return referenced file paths.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Deduplicated list of file path strings in order of first appearance.
    """
    if os.environ.get("USE_LEGACY_PARSER", "false").lower() == "true":
        seen: set = set()
        result: List[str] = []
        masked = _mask_fenced_blocks(runbook_content)
        for path in re.findall(r'####\s*\[MODIFY\]\s*`?([^\n`]+)`?', masked, re.IGNORECASE):
            path = _unescape_path(path)
            if path not in seen:
                seen.add(path)
                result.append(path)
        return result

    # AST implementation
    try:
        steps = _extract_runbook_data_ast(runbook_content)
    except ValueError:
        return []
        
    paths = []
    seen = set()
    for step in steps:
        for op in step["operations"]:
            if "blocks" in op and op["path"] not in seen:
                paths.append(op["path"])
                seen.add(op["path"])
    return paths


def extract_approved_files(runbook_content: str) -> Set[str]:
    """Extract all declared file paths from [MODIFY], [NEW], and [DELETE] headers.

    This is the approved file set for scope-bounding (INFRA-136 AC-2).

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Set of file path strings declared in the runbook.
    """
    if os.environ.get("USE_LEGACY_PARSER", "false").lower() == "true":
        paths: Set[str] = set()
        masked = _mask_fenced_blocks(runbook_content)
        for match in re.findall(
            r'####\s*\[(?:MODIFY|NEW|DELETE)\]\s*`?([^\n`]+)`?',
            masked, re.IGNORECASE,
        ):
            paths.add(_unescape_path(match))
        return paths

    # AST implementation
    try:
        steps = _extract_runbook_data_ast(runbook_content)
    except ValueError:
        return set()
        
    approved_paths = set()
    for step in steps:
        for op in step["operations"]:
            approved_paths.add(op["path"])
    return approved_paths


def extract_cross_cutting_files(runbook_content: str) -> Set[str]:
    """Extract file paths annotated with cross_cutting: true (INFRA-136 AC-4).

    Recognises ``<!-- cross_cutting: true -->`` on the line before or after
    a ``[MODIFY]``/``[NEW]`` header.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Set of file path strings with cross_cutting relaxation.
    """
    paths: Set[str] = set()
    masked = _mask_fenced_blocks(runbook_content)
    for match in re.findall(
        r'<!--\s*cross_cutting:\s*true\s*-->\s*\n'
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?',
        masked, re.IGNORECASE,
    ):
        paths.add(_unescape_path(match))
    for match in re.findall(
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?\s*\n'
        r'\s*<!--\s*cross_cutting:\s*true\s*-->',
        masked, re.IGNORECASE,
    ):
        paths.add(_unescape_path(match))
    return paths


def detect_malformed_modify_blocks(content: str) -> List[str]:
    """Detect [MODIFY] headers that have a full code block but no S/R blocks.

    [MODIFY] must always use <<<SEARCH/===/>>> blocks. A [MODIFY] with a full
    code block is silently unreachable: parse_code_blocks excludes [MODIFY]
    headers, and parse_search_replace_blocks finds no <<<SEARCH marker.
    This function surfaces that contract violation loudly so the developer
    knows their runbook is malformed rather than seeing a silent no-op.

    Args:
        content: Runbook or AI-generated chunk text.

    Returns:
        List of file paths where [MODIFY] + full code block exists without
        any accompanying <<<SEARCH block.
    """
    malformed: List[str] = []
    file_sections = re.split(
        r'(?:^|\n)(?:(?:File|Modify):\s*|####\s*\[MODIFY\]\s*)`?([^\n`]+?)`?\s*\n',
        content, flags=re.IGNORECASE,
    )
    for i in range(1, len(file_sections), 2):
        filepath = _unescape_path(file_sections[i])
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        has_sr = bool(re.search(r'<<<SEARCH', body))
        has_full_block = bool(re.search(r'```[\w]*\n', body))
        if has_full_block and not has_sr:
            malformed.append(filepath)
    return malformed


def _mask_fenced_blocks(text: str) -> str:
    """Replace fenced code block content with spaces to preserve character offsets.

    This prevents ``#### [MODIFY|NEW|DELETE]`` patterns inside code blocks
    (e.g. test data or documentation) from being matched as real operation
    headers during step parsing.

    Uses balanced fence detection (length matching) and start-of-line anchoring
    so nested blocks (common in ADRs) do not cause premature closure.

    Args:
        text: Raw markdown text.

    Returns:
        Same-length string with code block interiors replaced by spaces.
    """
    def _replacer(m: re.Match) -> str:
        return ' ' * len(m.group(0))

    # (?m) for multiline mode (anchor ^ and $ to line starts/ends)
    # 1. Matches 0-3 leading spaces followed by 3+ backticks or tildes.
    # 2. Captures fence content in 'fence' group.
    # 3. Matches content non-greedily.
    # 4. Matches a closing fence of the SAME length at start-of-line.
    pattern = r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[^\n]*\n(.*?)\n\1(?P=fence)[ \t]*(?:\n|$)'
    return re.sub(pattern, _replacer, text, flags=re.DOTALL)


def _extract_fenced_content(block_body: str) -> str:
    """Extract content from a fenced code block, handling nested fences.

    Scans line-by-line for the first opening fence and the **last**
    closing fence with the same characters and indentation. Inner
    closing fences (same backtick length) are skipped because the
    last match wins.

    Args:
        block_body: Markdown body after a ``[NEW]`` header.

    Returns:
        Extracted content, or empty string if no valid fence pair.
    """
    lines = block_body.split('\n')
    fence_re = re.compile(r'^( {0,3})(`{3,}|~{3,})')
    opening_fence = None
    opening_indent = None
    content_start = None
    last_close = None

    for i, line in enumerate(lines):
        m = fence_re.match(line)
        if m is None:
            continue
        indent = m.group(1)
        fence_chars = m.group(2)
        rest = line[m.end():]

        if opening_fence is None:
            opening_fence = fence_chars
            opening_indent = indent
            content_start = i + 1
        elif fence_chars == opening_fence and indent == opening_indent:
            if rest.strip() == "":
                last_close = i

    if content_start is not None and last_close is not None and last_close > content_start:
        return '\n'.join(lines[content_start:last_close]).rstrip()
    return ""


def _extract_runbook_data_ast(content: str) -> List[RunbookStepDict]:
    """Extract implementation steps using an AST parser.

    Uses mistune to parse markdown into tokens and walks the tree to identify
    structural headers (H2 Implementation Steps -> H3 Steps -> H4 Operations).

    Args:
        content: Raw runbook markdown text.

    Returns:
        List of structured step dictionaries.

    Raises:
        ValueError: If Implementation Steps section is missing.
        ParsingError: If operation blocks are malformed.
    """
    # Pre-process content to protect SEARCH/REPLACE blocks.
    # Mistune 3 splits text with blank lines into separate paragraph tokens, which
    # destroys the structural integrity of <<<SEARCH/REPLACE blocks that contain blank lines.
    # We wrap them in HTML comments so Mistune parses them as a single `block_html` token,
    # perfectly preserving their exact internal newlines and whitespace.
    def _protect_sr(m: re.Match) -> str:
        return f"<!--XYZ_SEARCH_START\n{m.group(1)}\n===\n{m.group(2)}\nXYZ_SEARCH_END-->"
    content = re.sub(
        r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$',
        _protect_sr, content, flags=re.DOTALL
    )
    
    markdown = mistune.create_markdown(renderer=None)
    tokens = markdown(content)

    def _children_text(token: dict) -> str:
        """Extract concatenated text from token children, preserving bold/em delimiters.

        mistune v3 parses ``__init__`` as a ``strong`` token wrapping a ``text``
        child.  Silently dropping the ``strong`` wrapper loses the underscores and
        produces ``init`` instead of ``__init__``.  We restore the original
        delimiters so file paths like ``__init__.py`` survive the round-trip.
        """
        parts = []
        for t in token.get('children', []):
            ttype = t.get('type')
            if ttype == 'text':
                parts.append(t.get('raw', ''))
            elif ttype == 'codespan':
                parts.append(t.get('raw', ''))
            elif ttype == 'strong':
                # Re-wrap with __ so _unescape_path can convert ** back to __
                inner = _children_text(t)
                parts.append(f'__{inner}__')
            elif ttype == 'emphasis':
                inner = _children_text(t)
                parts.append(f'_{inner}_')
            elif ttype in ('softbreak', 'hardbreak'):
                parts.append('\n')
        return ''.join(parts).strip()

    steps: List[RunbookStepDict] = []
    current_step: Optional[dict] = None
    current_op: Optional[dict] = None
    in_impl_steps = False

    for token in tokens:
        # 1. Identify "Implementation Steps" (H2)
        if token['type'] == 'heading' and token['attrs']['level'] == 2:
            header_text = _children_text(token)
            if header_text.lower() == "implementation steps":
                in_impl_steps = True
                continue
            elif in_impl_steps:
                # Exit if we hit another H2 after Implementation Steps
                break

        if not in_impl_steps:
            continue

        # 2. Identify Step (H3)
        if token['type'] == 'heading' and token['attrs']['level'] == 3:
            title = _children_text(token)
            # Strip "Step N: " prefix if present
            title = re.sub(r'^Step\s+\d+:\s*', '', title, flags=re.IGNORECASE)
            current_step = {"title": title, "operations": []}
            steps.append(current_step)
            current_op = None
            continue

        # 3. Identify Operation (H4)
        if token['type'] == 'heading' and token['attrs']['level'] == 4:
            op_text = _children_text(token)
            match = re.match(r'\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?\s*$', op_text, re.IGNORECASE)
            if match and current_step is not None:
                action = match.group(1).upper()
                filepath = _unescape_path(match.group(2))
                current_op = {"action": action, "path": filepath}
                if action == "MODIFY":
                    current_op["blocks"] = []
                elif action == "NEW":
                    current_op["content"] = ""
                elif action == "DELETE":
                    current_op["rationale"] = ""
                current_step["operations"].append(current_op)
            continue

        # 4. Extract content for the current operation
        if current_op and token['type'] in ('paragraph', 'block_code', 'text', 'block_html'):
            # Text content extraction from various token structures
            text_parts = []
            if 'raw' in token:
                text_parts.append(token['raw'])
            elif 'children' in token:
                text_parts.append(_children_text(token))
            
            body_text = "\n".join(text_parts).strip()
            if not body_text:
                continue

            if current_op["action"] == "MODIFY":
                # Look for SEARCH/REPLACE blocks using the protected sentinel
                sr_pattern = r'(?m)^<!--XYZ_SEARCH_START\n(.*?)\n===\n(.*?)\nXYZ_SEARCH_END-->'
                for sr in re.finditer(sr_pattern, body_text, re.DOTALL):
                    current_op["blocks"].append({"search": sr.group(1), "replace": sr.group(2)})
            
            elif current_op["action"] == "NEW" and token['type'] == 'block_code':
                # For NEW, we only take the first code block encountered under the H4
                if not current_op["content"]:
                    current_op["content"] = body_text.rstrip()
            
            elif current_op["action"] == "DELETE":
                # Strip HTML comments and accumulate rationale
                rationale = re.sub(r'<!--\s*|\s*-->', '', body_text).strip()
                if rationale:
                    current_op["rationale"] = (current_op["rationale"] + " " + rationale).strip()

    if not steps and in_impl_steps:
         # Check if there were any operations at all
         pass
    elif not in_impl_steps:
        raise ValueError("Missing '## Implementation Steps' section — runbook has no executable steps.")

    # Validation: Flag (but don't crash on) malformed blocks so downstream
    # consumers can handle them as correctable gate findings.
    for step in steps:
        for op in step["operations"]:
            if op.get("action") == "MODIFY" and not op.get("blocks"):
                _logger.warning(
                    "malformed_modify_block",
                    extra={"path": op["path"], "reason": "no SEARCH/REPLACE blocks"},
                )
                op["malformed"] = True
            if op.get("action") == "NEW" and not op.get("content"):
                _logger.warning(
                    "malformed_new_block",
                    extra={"path": op["path"], "reason": "no code block"},
                )
                op["malformed"] = True
            # Remove the internal 'action' key used for parsing state
            op.pop("action", None)

    return steps


def _extract_runbook_data_legacy(content: str) -> List[dict]:
    """Extract implementation steps using legacy regex logic (Rollback path).

    Args:
        content: Raw runbook markdown text.

    Returns:
        List of step dicts.
    """
    if not re.search(r'^##\s+Implementation Steps', content, re.MULTILINE):
        raise ValueError(
            "Missing '## Implementation Steps' section — runbook has no executable steps."
        )

    impl_match = re.search(
        r'^## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
        re.DOTALL | re.MULTILINE,
    )
    body = impl_match.group(1) if impl_match else ""

    step_splits = re.split(r'(?:^|\n)### ', body)
    steps: List[dict] = []

    for raw_step in step_splits[1:]:
        title_match = re.match(r'(?:Step\s+\d+:\s*)?(.+)', raw_step.splitlines()[0])
        title = title_match.group(1).strip() if title_match else "Untitled Step"

        masked_step = _mask_fenced_blocks(raw_step)
        block_pattern = re.compile(
            r'####\s*\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?[ \t]*\n',
            re.IGNORECASE,
        )
        block_matches = list(block_pattern.finditer(masked_step))
        operations: List[dict] = []

        for idx, match in enumerate(block_matches):
            action = match.group(1).upper()
            filepath = _unescape_path(match.group(2))
            start = match.end()
            end = block_matches[idx + 1].start() if idx + 1 < len(block_matches) else len(raw_step)
            block_body = raw_step[start:end]

            if action == "MODIFY":
                sr_blocks = []
                sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                for sr in re.finditer(sr_pattern, block_body, re.DOTALL):
                    sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                if not sr_blocks:
                    raise ParsingError(
                        f"MODIFY header for '{filepath}' found but no valid SEARCH/REPLACE blocks."
                    )
                operations.append({"path": filepath, "blocks": sr_blocks})

            elif action == "NEW":
                file_content = _extract_fenced_content(block_body)
                if not file_content:
                    raise ParsingError(f"NEW header for '{filepath}' found but no code fence matched.")
                operations.append({"path": filepath, "content": file_content})

            elif action == "DELETE":
                rationale = block_body.strip()
                rationale = re.sub(r'<!--\s*|\s*-->', '', rationale).strip()
                operations.append({"path": filepath, "rationale": rationale or ""})

        if operations:
            steps.append({"title": title, "operations": operations})

    return steps


def _extract_runbook_data(content: str) -> List[dict]:
    """Extract implementation steps from runbook markdown into structured dicts.

    Dispatches to either AST or Legacy parser based on USE_LEGACY_PARSER env var.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of step dicts suitable for RunbookSchema.
    """
    use_legacy = os.environ.get("USE_LEGACY_PARSER", "false").lower() == "true"
    span_ctx = _tracer.start_as_current_span("runbook.extract_data") if _tracer else contextlib.nullcontext()
    
    with span_ctx as span:
        line_count = len(content.splitlines())
        if span:
            span.set_attribute("parser.mode", "legacy" if use_legacy else "ast")
            span.set_attribute("runbook.line_count", line_count)
            
        if use_legacy:
            steps = _extract_runbook_data_legacy(content)
        else:
            steps = _extract_runbook_data_ast(content)

        if span:
            span.set_attribute("runbook.step_count", len(steps))
            # Calculate and record block mapping density (INFRA-168)
            density = (len(steps) / max(1, line_count)) * 100
            span.set_attribute("runbook.block_density", density)
            _logger.info(
                "skeleton_parsed",
                extra={
                    "block_count": len(steps),
                    "line_count": line_count,
                    "density": f"{density:.2f}%"
                }
            )

        return steps


def _check_python_syntax(step_data: List[dict]) -> List[str]:
    """Validate Python syntax in [NEW] blocks using ast.parse().

    Iterates over extracted step data and runs ``ast.parse()`` on any
    ``[NEW]`` block whose path ends with ``.py``. Errors are returned
    as non-blocking warning strings and emitted to ``stderr``.

    Args:
        step_data: List of step dicts from ``_extract_runbook_data``.

    Returns:
        List of syntax warning strings. Empty if all valid.
    """
    warnings: List[str] = []
    for step in step_data:
        for op in step.get("operations", []):
            path = op.get("path", "")
            content = op.get("content", "")
            if not content or not path.endswith(".py"):
                continue
            try:
                ast.parse(content, filename=path)
            except SyntaxError as exc:
                msg = (
                    f"Python syntax error in [NEW] {path}: "
                    f"{exc.msg} (line {exc.lineno})"
                )
                warnings.append(msg)
                _logger.warning(
                    "python_syntax_warning",
                    extra={"path": path, "error": exc.msg, "line_number": exc.lineno},
                )
                print(f"⚠️  {msg}", file=sys.stderr)
    return warnings


def validate_runbook_schema(content: str) -> List[str]:
    """Validate a runbook's implementation block structure using Pydantic models.

    Extracts the ``## Implementation Steps`` section, parses it into
    structured dictionaries, and validates against :class:`RunbookSchema`.
    Returns a list of human-readable violations preserving the ``List[str]``
    contract expected by callers.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of violation strings. Empty list means schema is valid.
    """
    violations: List[str] = []
    span_ctx = _tracer.start_as_current_span("runbook.validate_schema") if _tracer else contextlib.nullcontext()
    with span_ctx as span:
        try:
            step_data = _extract_runbook_data(content)
            RunbookSchema(steps=step_data)
        except ValidationError as exc:
            for error in exc.errors():
                loc = " -> ".join(str(item) for item in error["loc"])
                violations.append(f"[{loc}]: {error['msg']}")
        except ValueError as exc:
            violations.append(str(exc))
        except Exception as exc:
            violations.append(f"Structural error: {exc}")

        # INFRA-151: Python syntax validation (non-blocking warnings)
        if not violations:
            try:
                syntax_warnings = _check_python_syntax(step_data)
                if syntax_warnings:
                    _logger.info(
                        "python_syntax_check",
                        extra={
                            "warning_count": len(syntax_warnings),
                            "warnings": syntax_warnings,
                        },
                    )
                if span and syntax_warnings:
                    span.set_attribute("runbook.syntax_warning_count", len(syntax_warnings))
            except Exception as exc:
                _logger.warning("python_syntax_check_error: %s", exc)

        if span:
            span.set_attribute("runbook.violation_count", len(violations))

    return violations


def split_runbook_into_chunks(content: str) -> Tuple[str, List[str]]:
    """Split a runbook into a global context header and per-step chunks.

    Also appends Definition of Done and Verification Plan as trailing chunks
    so documentation and test requirements are processed by the AI.

    Args:
        content: Full runbook markdown string.

    Returns:
        Tuple of ``(global_context, list_of_step_chunks)``.
    """
    impl_headers = ["## Implementation Steps", "## Proposed Changes", "## Changes"]
    start_idx = -1
    for header in impl_headers:
        if header in content:
            start_idx = content.find(header)
            break
    if start_idx == -1:
        return content, [content]
    global_context = content[:start_idx].strip()
    body = content[start_idx:]
    raw_chunks = re.split(r'\n### ', body)
    header_part = raw_chunks[0]
    chunks: List[str] = [
        f"{header_part}\n### {raw_chunks[i]}" for i in range(1, len(raw_chunks))
    ]
    if not chunks:
        chunks = [body]
    dod = re.search(r'(## Definition of Done.*?)(?=\n## |$)', content, re.DOTALL)
    if dod:
        chunks.append(f"DOCUMENTATION AND COMPLETION REQUIREMENTS:\n{dod.group(1).strip()}")
    verify = re.search(r'(## Verification Plan.*?)(?=\n## |$)', content, re.DOTALL)
    if verify:
        chunks.append(f"TEST REQUIREMENTS:\n{verify.group(1).strip()}")
    return global_context, chunks


def parse_skeleton(content: str, source_path: Optional[str] = None) -> RunbookSkeleton:
    """Decompose a template string into addressable blocks with metadata mapping.

    Recognises blocks bounded by HTML-style comments:
    <!-- block: id key=value -->
    Content
    <!-- /block -->

    Args:
        content: Raw template string.
        source_path: Optional path to the source file for reference.

    Returns:
        A RunbookSkeleton containing the mapped blocks.

    Raises:
        InvalidTemplateError: If no blocks are found, IDs are duplicated,
                             or block structure is malformed.
    """
    # Pattern captures block ID, metadata, and the raw inner content.
    pattern = re.compile(
        r'<!--\s*block:\s*(?P<id>[\w-]+)\s*(?P<meta>.*?)\s*-->(?P<content>.*?)<!--\s*/block\s*-->',
        re.DOTALL
    )

    matches = list(pattern.finditer(content))
    if not matches:
        raise InvalidTemplateError(
            "No addressable blocks found. Templates must contain markers in the format: "
            "<!-- block: id --> content <!-- /block -->"
        )

    blocks: List[RunbookBlock] = []
    seen_ids = set()
    last_pos = 0

    for i, match in enumerate(matches):
        block_id = match.group('id')
        if block_id in seen_ids:
            raise InvalidTemplateError(f"Duplicate block ID '{block_id}' found in skeleton.")
        seen_ids.add(block_id)

        # Metadata extraction: key=value (supports underscores and dots in values)
        meta_raw = match.group('meta')
        metadata = {}
        if meta_raw:
            kv_pairs = re.findall(r'(\w+)=["\']?([\w.-]+)["\']?', meta_raw)
            metadata = {k: v for k, v in kv_pairs}

        # Assign prefix whitespace (text between previous block end and current tags)
        prefix = content[last_pos:match.start()]
        
        # Suffix whitespace (remaining text after the last block tag)
        suffix = ""
        if i == len(matches) - 1:
            suffix = content[match.end():]

        blocks.append(RunbookBlock(
            id=block_id,
            content=match.group('content'),
            metadata=metadata,
            prefix_whitespace=prefix,
            suffix_whitespace=suffix,
            block_type="markdown"
        ))
        last_pos = match.end()

    return RunbookSkeleton(blocks=blocks, source_path=source_path)
