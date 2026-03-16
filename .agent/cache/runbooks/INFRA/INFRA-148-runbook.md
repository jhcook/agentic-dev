# INFRA-148: Parser Robustness & Path Escaping

## State

ACCEPTED

## Goal Description

Enhance the documentation and runbook parser to handle complex markdown structures and technical file paths correctly. This involves implementing balanced code fence detection to prevent premature closure when processing nested backticks (common in ADRs), and adding automatic unescaping for file paths in headers to ensure technical accuracy for files like `__init__.py`. The fix also includes improved observability through debug logging for regex matching failures.

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- The move to balanced fence detection (matching opening and closing fence lengths) is a positive architectural improvement that aligns with CommonMark standards and enhances parser robustness.
- Consolidating path cleaning logic into the `_unescape_path` helper function improves modularity within the parser component.
- Changes are localized to the implementation parser, maintaining architectural boundaries.

### @Qa
- The story includes a comprehensive verification plan with specific new test cases for nested backtick handling and path unescaping, satisfying requirements for a robust test strategy.
- Scenarios 1 (balanced detection) and 2 (unescaping) are explicitly addressed.

### @Security
- Security checks pass; logging does not introduce PII.
- Regex changes for parsing robustness do not introduce new vulnerabilities in the local CLI context.

### @Product
- Clear, testable acceptance criteria and a complete Impact Analysis ensure the value of improved parser robustness is delivered to the user.
- Build pipeline stability is improved by preventing parser crashes on malformed AI output.

### @Observability
- The implementation correctly uses the centralized `get_logger` factory for structured, standard-compliant logging.
- New `_logger.debug` statements provide critical context (e.g., `filepath`) when blocks cannot be successfully parsed, reducing support overhead for "silent failures".

### @Docs
- **Required Action**: Update `CHANGELOG.md` with the entry "Improved markdown parser robustness for nested ADR blocks and technical file paths." and mark the corresponding DoD item as complete.
- Documentation parser changes are self-documenting in code via PEP-257 docstrings.

### @Compliance
- License headers are preserved.
- No personal data handling changes; data processing remains purely technical.

### @Mobile
- Not applicable; changes are confined to the backend Python parser.

### @Web
- No direct impact on frontend code or React components; ensures cleaner data for potential future frontend documentation linking.

### @Backend
- Strict type enforcement is maintained for Pydantic models through correct use of type hints in new and modified functions.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/core/implement/parser.py`: The core implementation of the runbook and search/replace parser.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/test_parser.py` | `agent.core.implement.parser` | `agent.core.implement.parser` | Update unit tests to include nested backticks and escaped paths. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Step Title Extraction | `_extract_runbook_data` | `### Step N: Title` | Yes |
| S/R Block Format | `parse_search_replace_blocks` | `<<<SEARCH / === / >>>` | Yes |
| Header Action Markers | `extract_approved_files` | `[MODIFY], [NEW], [DELETE]` | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Consolidate path cleaning and unescaping logic into a internal helper function.
- [x] Refactor `_mask_fenced_blocks` to use a more robust fence-length matching pattern.

## Implementation Steps

### Step 1: Add imports and unescape helper

Add `get_logger` for observability and implement the `_unescape_path` helper to handle technical characters and markdown styling in headers.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
import contextlib
import re
from typing import Dict, List, Set, Tuple, Union, Optional

from pydantic import ValidationError
===
import contextlib
import re
import logging
from typing import Dict, List, Set, Tuple, Union, Optional

from pydantic import ValidationError

from agent.core.logger import get_logger
>>>
<<<SEARCH
_tracer = None


def parse_code_blocks(content: str) -> List[Dict[str, str]]:
===
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
>>>
```

### Step 2: Fix nested backticks in `parse_code_blocks`

Update the regex to ensure code blocks only close on a fence of the same length at the start of a line, preventing premature closure in ADRs.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
    blocks: List[Dict[str, str]] = []
    for match in re.finditer(r'```[\w]+:([\w/\.\-_]+)\n(.*?)```', content, re.DOTALL):
        blocks.append({"file": match.group(1).strip(), "content": match.group(2).strip()})
    # [NEW] only — [MODIFY] blocks are handled exclusively by parse_search_replace_blocks.
    # This prevents double-processing and avoids the docstring gate rejecting S/R-only steps.
    p2 = r'(?:(?:File|Create):\s*|####\s*\[(?:NEW|ADD)\]\s*)`?([^\n`]+?)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = match.group(1).strip()
===
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
>>>
```

### Step 3: Implement balanced masking and path unescaping in headers

Update `_mask_fenced_blocks` to correctly handle nested fences and update extraction functions to use `_unescape_path`.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
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
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result
===
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
>>>
<<<SEARCH
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
        paths.add(match.strip())
    return paths
===
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
>>>
```

### Step 4: Fix `extract_cross_cutting_files` and `detect_malformed_modify_blocks`

Ensure cross-cutting path extraction and malformed block detection also respect path unescaping.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
    for match in re.findall(
        r'<!--\s*cross_cutting:\s*true\s*-->\s*\n'
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?',
        masked, re.IGNORECASE,
    ):
        paths.add(match.strip())
    for match in re.findall(
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?\s*\n'
        r'\s*<!--\s*cross_cutting:\s*true\s*-->',
        masked, re.IGNORECASE,
    ):
        paths.add(match.strip())
    return paths
===
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
>>>
<<<SEARCH
    for i in range(1, len(file_sections), 2):
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        has_sr = bool(re.search(r'<<<SEARCH', body))
        has_full_block = bool(re.search(r'```[\w]*\n', body))
        if has_full_block and not has_sr:
            malformed.append(filepath)
    return malformed
===
    for i in range(1, len(file_sections), 2):
        filepath = _unescape_path(file_sections[i])
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        has_sr = bool(re.search(r'<<<SEARCH', body))
        has_full_block = bool(re.search(r'```[\w]*\n', body))
        if has_full_block and not has_sr:
            malformed.append(filepath)
    return malformed
>>>
```

### Step 5: Update `_mask_fenced_blocks` with balanced fence logic

Update the internal masking function to correctly identify and hide outer code blocks, preventing headers inside them from being matched as operations.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
def _mask_fenced_blocks(text: str) -> str:
    """Replace fenced code block content with spaces to preserve character offsets.

    This prevents ``#### [MODIFY|NEW|DELETE]`` patterns inside code blocks
    (e.g. test data or documentation) from being matched as real operation
    headers during step parsing.

    Uses start-of-line anchoring for fence delimiters so backticks inside
    code block content (e.g. Python string literals) don't cause premature
    fence closure.

    Args:
        text: Raw markdown text.

    Returns:
        Same-length string with code block interiors replaced by spaces.
    """
    def _replacer(m: re.Match) -> str:
        return ' ' * len(m.group(0))
    return re.sub(
        r'(?:^|\n)```[\w]*\n.*?(?:^|\n)```',
        _replacer, text, flags=re.DOTALL | re.MULTILINE,
    )
===
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
>>>
```

### Step 6: Robust step parsing with path unescaping and observability

Update `_extract_runbook_data` to unescape paths, handle balanced fences for `NEW` blocks, and add debug logging for failures.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
            for idx, match in enumerate(block_matches):
                action = match.group(1).upper()
                filepath = match.group(2).strip()
                start = match.end()
                end = block_matches[idx + 1].start() if idx + 1 < len(block_matches) else len(raw_step)
                block_body = raw_step[start:end]

                if action == "MODIFY":
                    sr_blocks = []
                    for sr in re.finditer(r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', block_body, re.DOTALL):
                        sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    fence_match = re.search(r'```[\w]*\n(.*?)```', block_body, re.DOTALL)
                    file_content = fence_match.group(1).rstrip() if fence_match else ""
                    operations.append({"path": filepath, "content": file_content})
===
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
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/core/implement/tests/test_parser.py`: Verify that all existing parser tests pass.
- [ ] New Test Case: Create a test string with nested backticks (4 wrapping 3) and verify `_extract_runbook_data` captures the full inner content.
- [ ] New Test Case: Create a test string with `#### [MODIFY] src/\_\_init\_\_.py` and verify extracted path is `src/__init__.py`.
- [ ] New Test Case: Verify `#### [MODIFY] **path/to/file.py**` extracts `path/to/file.py`.

### Manual Verification

- [ ] Create a local runbook with a `[NEW]` block containing a full ADR (including code blocks) and run `agent implement --dry-run` to confirm the ADR content is not truncated.
- [ ] Verify logs: Run `agent implement` on a malformed runbook and check `.agent/logs/agent.log` for the new debug messages.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with "Improved markdown parser robustness for nested ADR blocks and technical file paths."
- [ ] Docstrings in `parser.py` updated to reflect balanced fence detection logic.

### Observability

- [ ] Logs are structured and free of PII
- [ ] New debug logging uses `_logger.debug` and includes relevant context (filepath).

### Testing

- [ ] All existing tests pass
- [ ] New tests added for nested backticks and path unescaping.

## Copyright

Copyright 2026 Justin Cook
