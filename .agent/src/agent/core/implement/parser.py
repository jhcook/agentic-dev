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

import contextlib
import re
import logging
from typing import Dict, List, Set, Tuple, Union, Optional

from pydantic import ValidationError

from agent.core.logger import get_logger

from agent.core.implement.models import (
    RunbookSchema,
    RunbookStep,
    ModifyBlock,
    NewBlock,
    DeleteBlock,
    SearchReplaceBlock,
)

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None
_logger = get_logger(__name__)


def _unescape_path(path: str) -> str:
    """Remove markdown escapes and styling from file paths.

    Handles cases like `**path/to/__init__.py**` or `path/to/\_\_init\_\_.py`
    by stripping markers and removing backslash escapes.

    Args:
        path: Raw path string from markdown header.

    Returns:
        Clean, technical file path.
    """
    if not path:
        return ""
    # Remove bold/italic and backticks
    path = path.strip().strip('`*')
    # Remove backslash escapes for markdown characters: _ * [ ] ( ) # + - . !
    return re.sub(r'\\([_*[\]()#+\-.!])', r'\1', path)


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
        blocks.append({"file": _unescape_path(match.group(3)), "content": match.group(4).strip()})

    # [NEW] only — [MODIFY] blocks are handled exclusively by parse_search_replace_blocks.
    # Pattern 2: Header followed by ``` code block
    p2 = (
        r'(?m)(?:(?:File|Create):\s*|####\s*\[(?:NEW|ADD)\]\s*)`?([^\n`]+?)`?\s*\n'
        r'( {0,3})(?P<fence2>`{3,}|~{3,})[\w]*\n(.*?)\n\2(?P=fence2)[ \t]*$'
    )
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = _unescape_path(match.group(1))
        block_content = match.group(2).strip()
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
        filepath = file_sections[i].strip()
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
    seen: set = set()
    result: List[str] = []
    masked = _mask_fenced_blocks(runbook_content)
    for path in re.findall(r'####\s*\[MODIFY\]\s*`?([^\n`]+)`?', masked, re.IGNORECASE):
        path = _unescape_path(path)
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def extract_approved_files(runbook_content: str) -> Set[str]:
    """Extract all declared file paths from [MODIFY], [NEW], and [DELETE] headers.

    This is the approved file set for scope-bounding (INFRA-136 AC-2).

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Set of file path strings declared in the runbook.
    """
    paths: Set[str] = set()
    masked = _mask_fenced_blocks(runbook_content)
    for match in re.findall(
        r'####\s*\[(?:MODIFY|NEW|DELETE)\]\s*`?([^\n`]+)`?',
        masked, re.IGNORECASE,
    ):
        paths.add(_unescape_path(match))
    return paths


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


def _extract_runbook_data(content: str) -> List[dict]:
    """Extract implementation steps from runbook markdown into Pydantic-ready dicts.

    Parses ``## Implementation Steps`` to find ``### Step N`` headers,
    then within each step finds ``#### [MODIFY|NEW|DELETE]`` blocks and
    extracts their content into structured dictionaries.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of step dicts suitable for ``RunbookSchema(steps=...)``.

    Raises:
        ValueError: If the ``## Implementation Steps`` section is missing.
    """
    span_ctx = _tracer.start_as_current_span("runbook.extract_data") if _tracer else contextlib.nullcontext()
    with span_ctx as span:
        if not re.search(r'^##\s+Implementation Steps', content, re.MULTILINE):
            raise ValueError(
                "Missing '## Implementation Steps' section — runbook has no executable steps."
            )

        impl_match = re.search(
            r'## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
            re.DOTALL | re.MULTILINE,
        )
        body = impl_match.group(1) if impl_match else ""

        # Split into steps by ### headers (handle body with or without leading newline)
        step_splits = re.split(r'(?:^|\n)### ', body)
        steps: List[dict] = []

        for raw_step in step_splits[1:]:  # skip preamble before first ###
            title_match = re.match(r'(?:Step\s+\d+:\s*)?(.+)', raw_step.splitlines()[0])
            title = title_match.group(1).strip() if title_match else "Untitled Step"

            # Mask fenced code blocks so embedded #### [MODIFY] etc. in
            # file content (e.g. test data) are not matched as operations.
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
                    # Also require >>> to be at start of line for robustness
                    sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                    for sr in re.finditer(sr_pattern, block_body, re.DOTALL):
                        sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                    if not sr_blocks:
                        _logger.debug(f"Header found for {filepath} but no valid SEARCH/REPLACE blocks detected in body.")
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                         _logger.debug(f"NEW block for {filepath} found but no balanced code fence matched in body.")
                    operations.append({"path": filepath, "content": file_content})

                elif action == "DELETE":
                    rationale = block_body.strip()
                    # Strip HTML comments
                    rationale = re.sub(r'<!--\s*|\s*-->', '', rationale).strip()
                    operations.append({"path": filepath, "rationale": rationale or ""})

            if operations:
                steps.append({"title": title, "operations": operations})

        if span:
            span.set_attribute("runbook.step_count", len(steps))

        return steps


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
