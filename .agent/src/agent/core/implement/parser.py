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

import re
from typing import Dict, List, Tuple

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None


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
    for match in re.finditer(r'```[\w]+:([\w/\.\-_]+)\n(.*?)```', content, re.DOTALL):
        blocks.append({"file": match.group(1).strip(), "content": match.group(2).strip()})
    # [NEW] only — [MODIFY] blocks are handled exclusively by parse_search_replace_blocks.
    # This prevents double-processing and avoids the docstring gate rejecting S/R-only steps.
    p2 = r'(?:(?:File|Create):\s*|####\s*\[(?:NEW|ADD)\]\s*)`?([^\n`]+?)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = match.group(1).strip()
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
    for path in re.findall(r'\[MODIFY\]\s*`?([^\n`]+)`?', runbook_content, re.IGNORECASE):
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


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
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        has_sr = bool(re.search(r'<<<SEARCH', body))
        has_full_block = bool(re.search(r'```[\w]*\n', body))
        if has_full_block and not has_sr:
            malformed.append(filepath)
    return malformed


def validate_runbook_schema(content: str) -> List[str]:
    """Validate a runbook's implementation block structure against the format contract.

    Checks every ``#### [MODIFY]``, ``#### [NEW]``, and ``#### [DELETE]``
    block in the Implementation Steps section and returns a list of human-readable
    violations. An empty list means the runbook is structurally valid.

    Rules enforced:

    - ``[MODIFY] <path>``: must have at least one ``<<<SEARCH`` block.
      A bare fenced code block without ``<<<SEARCH`` is a contract violation.
    - ``[NEW] <path>``: must have a fenced code block. A ``<<<SEARCH``
      block without any code fence means the file content is missing.
      (Note: ``[NEW]`` + ``<<<SEARCH`` inside a fence is valid for idempotency
      and is handled by the S/R parser — it is not flagged here.)
    - ``[DELETE] <path>``: must have a non-empty body (rationale required).
    - The runbook must contain an ``## Implementation Steps`` section.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of violation strings. Empty list means schema is valid.
    """
    violations: List[str] = []

    # Rule 0: must have an implementation section
    if not re.search(r'^##\s+Implementation Steps', content, re.MULTILINE):
        violations.append(
            "Missing '## Implementation Steps' section — runbook has no executable steps."
        )
        return violations  # No point checking individual blocks without the section

    # Locate the implementation steps body
    impl_match = re.search(
        r'## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
        re.DOTALL | re.MULTILINE,
    )
    body = impl_match.group(1) if impl_match else ""

    # Split into individual action blocks: #### [ACTION] <path>
    block_pattern = re.compile(
        r'####\s*\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?\s*\n',
        re.IGNORECASE,
    )
    block_matches = list(block_pattern.finditer(body))

    for idx, match in enumerate(block_matches):
        action = match.group(1).upper()
        filepath = match.group(2).strip()
        # Block body is everything between this header and the next header (or end)
        start = match.end()
        end = block_matches[idx + 1].start() if idx + 1 < len(block_matches) else len(body)
        block_body = body[start:end]

        if action == "MODIFY":
            has_sr = bool(re.search(r'<<<SEARCH', block_body))
            if not has_sr:
                violations.append(
                    f"[MODIFY] '{filepath}': missing <<<SEARCH/===/>>> block. "
                    f"[MODIFY] must use search/replace, never a full code block."
                )

        elif action == "NEW":
            has_fence = bool(re.search(r'```[\w]*\n', block_body))
            if not has_fence:
                violations.append(
                    f"[NEW] '{filepath}': missing fenced code block. "
                    f"[NEW] must provide complete file content in a fenced block."
                )

        elif action == "DELETE":
            stripped = block_body.strip()
            if not stripped:
                violations.append(
                    f"[DELETE] '{filepath}': missing rationale. "
                    f"Add a one-line comment explaining why this file is removed."
                )

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
