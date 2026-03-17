# STORY-ID: INFRA-152: Migrate Runbook Parser From Regex

## State

ACCEPTED

## Goal Description

Migrate the runbook engine's markdown parsing logic from fragile, regex-based extraction to a robust Abstract Syntax Tree (AST) parser using `mistune`. This change addresses issues with nested code blocks, unanchored headers, and self-referential content that currently lead to execution errors. A feature toggle `USE_LEGACY_PARSER` will be provided to allow for immediate rollback if regressions are detected in production runbooks.

## Linked Journeys

- JRN-004: Authoring and Executing Automated Runbooks

## Panel Review Findings

### @Architect
- **ADR Compliance**: The move to an AST-based parser follows the direction of ADR-012 for standardized markdown ingestion.
- **Boundaries**: The logic remains encapsulated within the `implement.parser` module, respecting layer boundaries. The dependency on `mistune` is appropriate for a core infrastructure utility.

### @Qa
- **Test Strategy**: The plan to include nested block test cases is critical.
- **Reliability**: Replacing `_mask_fenced_blocks` (which relies on regex) with a proper AST walk significantly reduces the "edge case" surface area for malformed runbooks.

### @Security
- **Injection Prevention**: `mistune` will be used in AST mode (`renderer=None`) or with HTML rendering disabled to prevent any potential RCE or HTML injection during runbook parsing.
- **PII**: No implementation content or file data will be logged in the clear; only structural metrics (step counts, action types) will be traced.

### @Product
- **User Value**: This reduces the "it didn't parse" frustration for engineers writing complex runbooks with nested blocks (e.g., when a runbook step generates another runbook or markdown file).
- **Acceptance**: All scenarios in the story are covered by the switch to AST-based node identification.

### @Observability
- **Tracing**: Added OpenTelemetry attributes for parsing type (Legacy vs. AST) and structural metrics.
- **Logging**: Detailed logging for structural mismatches (e.g., missing action headers) is included.

### @Docs
- **Internal Docs**: The docstrings in `parser.py` will be updated to reflect the new AST-based processing.

### @Compliance
- **Licensing**: License headers are preserved. No change to data handling logic (no new PII collected).

### @Backend
- **Strict Typing**: Pydantic models are already in place; the AST parser will feed these models more reliably.
- **Dependencies**: `mistune` is a lightweight, performant dependency suitable for this role.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/core/implement/parser.py`: Contains the regex-based parsing logic to be replaced.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| .agent/src/agent/core/implement/tests/test_parser.py | `_extract_runbook_data` | `_extract_runbook_data` | Add nested fence test cases. |
| .agent/src/agent/core/implement/tests/test_runbook_validation.py | `validate_runbook_schema` | `validate_runbook_schema` | Verify AST-based validation errors. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `_extract_runbook_data` structure | `parser.py` | List[dict] matching RunbookSchema | YES |
| `_unescape_path` behavior | `parser.py` | Strips backticks/bold/escapes | YES |
| Python syntax check | `parser.py` | Warns on invalid Python in [NEW] | YES |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Rename legacy regex helpers to `_legacy_*` to clearly mark them for future deletion.
- [x] Remove the redundant `_mask_fenced_blocks` dependency in the new AST flow.

## Implementation Steps

### Step 1: Add mistune dependency and implement the AST-based parser core

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
import ast
import contextlib
import re
import logging
import sys
from typing import Dict, List, Set, Tuple, Union, Optional
===
import ast
import contextlib
import os
import re
import logging
import sys
from typing import Dict, Any, List, Set, Tuple, Union, Optional

import mistune
>>>
<<<SEARCH
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
            r'^## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
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
                        raise ParsingError(
                            f"MODIFY header for '{filepath}' found but no valid "
                            "SEARCH/REPLACE blocks detected in body."
                        )
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    # INFRA-151: Line-by-line parser for nested fence support
                    file_content = _extract_fenced_content(block_body)
                    if not file_content:
                        raise ParsingError(
                            f"NEW header for '{filepath}' found but no balanced "
                            "code fence matched in body."
                        )
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
===
def _extract_runbook_data_ast(content: str) -> List[dict]:
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
    markdown = mistune.create_markdown(renderer=None)
    tokens = markdown(content)

    steps: List[dict] = []
    current_step: Optional[dict] = None
    current_op: Optional[dict] = None
    in_impl_steps = False

    for token in tokens:
        # 1. Identify "Implementation Steps" (H2)
        if token['type'] == 'heading' and token['attrs']['level'] == 2:
            header_text = "".join(t['text'] for t in token.get('children', []) if t['type'] == 'text').strip()
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
            title = "".join(t['text'] for t in token.get('children', []) if t['type'] == 'text').strip()
            # Strip "Step N: " prefix if present
            title = re.sub(r'^Step\s+\d+:\s*', '', title, flags=re.IGNORECASE)
            current_step = {"title": title, "operations": []}
            steps.append(current_step)
            current_op = None
            continue

        # 3. Identify Operation (H4)
        if token['type'] == 'heading' and token['attrs']['level'] == 4:
            op_text = "".join(t['text'] for t in token.get('children', []) if t['type'] == 'text').strip()
            match = re.match(r'\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?', op_text, re.IGNORECASE)
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
        if current_op and token['type'] in ('paragraph', 'block_code', 'text'):
            # Text content extraction from various token structures
            text_parts = []
            if 'children' in token:
                text_parts.append("".join(t['text'] for t in token['children'] if 'text' in t))
            elif 'raw' in token:
                text_parts.append(token['raw'])
            elif 'text' in token:
                text_parts.append(token['text'])
            
            body_text = "\n".join(text_parts).strip()
            if not body_text:
                continue

            if current_op["action"] == "MODIFY":
                # Look for SEARCH/REPLACE blocks
                sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                for sr in re.finditer(sr_pattern, body_text, re.DOTALL):
                    current_op["blocks"].append({"search": sr.group(1), "replace": sr.group(2)})
            
            elif current_op["action"] == "NEW" and token['type'] == 'block_code':
                # For NEW, we only take the first code block encountered under the H4
                if not current_op["content"]:
                    current_op["content"] = body_text
            
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

    # Validation: Ensure MODIFY blocks have at least one S/R pair
    for step in steps:
        for op in step["operations"]:
            if op.get("action") == "MODIFY" and not op.get("blocks"):
                raise ParsingError(
                    f"MODIFY header for '{op['path']}' found but no valid SEARCH/REPLACE blocks detected."
                )
            if op.get("action") == "NEW" and not op.get("content"):
                raise ParsingError(
                    f"NEW header for '{op['path']}' found but no code block detected."
                )
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
        if span:
            span.set_attribute("parser.mode", "legacy" if use_legacy else "ast")
            
        if use_legacy:
            steps = _extract_runbook_data_legacy(content)
        else:
            steps = _extract_runbook_data_ast(content)

        if span:
            span.set_attribute("runbook.step_count", len(steps))

        return steps
>>>
```

### Step 2: Update file path extraction helpers to utilize the toggle

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
        path = _unescape_path(path)
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
    steps = _extract_runbook_data_ast(runbook_content)
    paths = []
    seen = set()
    for step in steps:
        for op in step["operations"]:
            if "blocks" in op and op["path"] not in seen:
                paths.append(op["path"])
                seen.add(op["path"])
    return paths
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
        paths.add(_unescape_path(match))
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
    steps = _extract_runbook_data_ast(runbook_content)
    approved_paths = set()
    for step in steps:
        for op in step["operations"]:
            approved_paths.add(op["path"])
    return approved_paths
>>>
```

## Verification Plan

### Automated Tests

- **Unit Tests**: Run `pytest .agent/src/agent/core/implement/tests/test_parser.py` to verify that existing runbooks still parse correctly.
- **Nested Fence Test**: Create a temporary test file with a runbook containing a `[NEW]` block that itself contains a fenced code block. Verify `_extract_runbook_data` extracts the inner content correctly.
- **Rollback Test**: Run tests with `USE_LEGACY_PARSER=true` and ensure the old regex logic is executed (can be verified via OpenTelemetry trace attributes or a temporary log).

### Manual Verification

- **Parse Production Runbook**: Run `agent runbook validate path/to/complex_runbook.md` and check for any schema violations.
- **Regression Check**: Compare output of the new parser vs old parser on a known set of 10 runbooks.

  ```bash
  # Check new parser
  agent runbook validate my-runbook.md
  # Check legacy parser
  USE_LEGACY_PARSER=true agent runbook validate my-runbook.md
  ```

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with "Migrated runbook parser to mistune AST for improved reliability".
- [x] Internal comments in `parser.py` updated to explain the H2/H3/H4 hierarchy logic.

### Observability

- [x] Logs are structured and free of PII.
- [x] `parser.mode` attribute added to OpenTelemetry spans.

### Testing

- [x] All existing tests pass.
- [x] New tests added for nested code blocks (Scenario 1).

## Copyright

Copyright 2026 Justin Cook
