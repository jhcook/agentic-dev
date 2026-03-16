# STORY-ID: INFRA-151: Python Syntax Validation & Testing

## State

ACCEPTED

## Goal Description

Add automated Python syntax validation for `[NEW]` code blocks in runbooks using `ast.parse()`, create a comprehensive negative test suite, and fix two parser fragilities: (1) the body extraction regex lacks `^` anchoring causing false matches inside code blocks, and (2) `[NEW]` block extraction uses a non-greedy regex that fails with nested fences.

## Linked Journeys

- JRN-004: Runbook Authoring and Deployment

## Panel Review Findings

### @Architect
- **VERDICT**: APPROVE
- **SUMMARY**: Clean extension to validation pipeline. The nested-fence and anchoring fixes address real parser fragilities exposed by INFRA-151's own runbook generation failure.

### @Security
- **VERDICT**: APPROVE
- **SUMMARY**: `ast.parse()` performs static analysis without executing code. No security concerns.

### @Qa
- **VERDICT**: APPROVE
- **SUMMARY**: Negative test suite covers all AC scenarios. Nested fence tests prevent regression.

### @Observability
- **VERDICT**: APPROVE
- **SUMMARY**: Syntax warnings use structured `extra={}` logging per repository standards.

## Codebase Introspection

### Targeted File Contents (from source)

#### .agent/src/agent/core/implement/parser.py (lines 17-20)
```python
import contextlib
import re
import logging
from typing import Dict, List, Set, Tuple, Union, Optional
```

#### .agent/src/agent/core/implement/parser.py (lines 341-353)
```python
                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = (
                        r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    )
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                        raise ParsingError(
                            f"NEW header for '{filepath}' found but no balanced "
                            "code fence matched in body."
                        )
                    operations.append({"path": filepath, "content": file_content})
```

#### .agent/src/agent/core/implement/parser.py (lines 384-401)
```python
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
```

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `validate_runbook_schema` returns `List[str]` | parser.py:370 | Empty list = valid | Yes |
| `_extract_runbook_data` raises `ParsingError` on missing fence | parser.py:349 | ParsingError | Yes |
| `_extract_runbook_data` raises `ValueError` on missing section | parser.py:293 | ValueError | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Anchor `impl_match` regex with `^` to prevent false matches inside code blocks
- [x] Replace non-greedy regex for `[NEW]` block extraction with line-by-line parser

## Implementation Steps

### Step 1: Anchor the body extraction regex

The `impl_match` regex lacks `^` so it matches `## Implementation Steps` inside code blocks and docstrings. Add the anchor.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
        impl_match = re.search(
            r'## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
            re.DOTALL | re.MULTILINE,
        )
===
        impl_match = re.search(
            r'^## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
            re.DOTALL | re.MULTILINE,
        )
>>>
```

### Step 2: Add `_extract_fenced_content` helper for nested fence support

Replace the non-greedy regex with a line-by-line parser that finds the last closing fence, correctly handling nested fences of the same backtick length.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = (
                        r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    )
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                        raise ParsingError(
                            f"NEW header for '{filepath}' found but no balanced "
                            "code fence matched in body."
                        )
                    operations.append({"path": filepath, "content": file_content})
===
                elif action == "NEW":
                    # INFRA-151: Line-by-line parser for nested fence support
                    file_content = _extract_fenced_content(block_body)
                    if not file_content:
                        raise ParsingError(
                            f"NEW header for '{filepath}' found but no balanced "
                            "code fence matched in body."
                        )
                    operations.append({"path": filepath, "content": file_content})
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
def _extract_runbook_data(content: str) -> List[dict]:
===
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


def _extract_runbook_data(content: str) -> List[dict]:
>>>
```

### Step 3: Add ast.parse syntax checking and integrate into validation

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
import contextlib
import re
import logging
from typing import Dict, List, Set, Tuple, Union, Optional
===
import ast
import contextlib
import re
import logging
import sys
from typing import Dict, List, Set, Tuple, Union, Optional
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
def validate_runbook_schema(content: str) -> List[str]:
===
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
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
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
===
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
            except Exception as exc:
                _logger.warning("python_syntax_check_error: %s", exc)

        if span:
            span.set_attribute("runbook.violation_count", len(violations))

    return violations
>>>
```

### Step 4: Create test suite

#### [NEW] .agent/src/agent/core/implement/tests/test_runbook_validation.py

```python
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

"""Negative test suite for runbook validation (INFRA-151).

Covers nested fences, missing code blocks, empty S/R, malformed
paths, missing headers, and Python syntax validation.
"""

import pytest

from agent.core.implement.parser import (
    _check_python_syntax,
    _extract_fenced_content,
    _extract_runbook_data,
    validate_runbook_schema,
)
from agent.core.implement.models import ParsingError


def _wrap_runbook(steps_body):
    """Wrap step content in a minimal valid runbook structure.

    Args:
        steps_body: Raw markdown under the header.

    Returns:
        Complete runbook markdown.
    """
    return (
        "# Runbook\n\n"
        "## Impl" + "ementation Steps\n\n"
        + steps_body
    )


# ── Nested fence support ─────────────────────────────────────


class TestExtractFencedContent:
    """Tests for _extract_fenced_content helper."""

    def test_simple_fence(self):
        """A simple fenced block with no nesting is extracted."""
        body = '```python\nprint("hello")\n```\n'
        assert _extract_fenced_content(body) == 'print("hello")'

    def test_nested_same_length_fences(self):
        """Inner fences of same backtick length are handled."""
        body = (
            '```python\n'
            'before\n'
            '```\n'
            'inner\n'
            '```\n'
            'after\n'
            '```\n'
        )
        result = _extract_fenced_content(body)
        assert 'before' in result
        assert 'inner' in result
        assert 'after' in result

    def test_no_fence_returns_empty(self):
        """Body with no fence returns empty string."""
        assert _extract_fenced_content("just prose\n") == ""

    def test_empty_fence_returns_empty(self):
        """Empty code fence returns empty string."""
        body = '```python\n```\n'
        assert _extract_fenced_content(body) == ""

    def test_tilde_fences(self):
        """Tilde fences are supported."""
        body = '~~~python\nprint("hi")\n~~~\n'
        assert _extract_fenced_content(body) == 'print("hi")'


# ── Missing code blocks in [NEW] tags (AC-3a) ────────────────


class TestNewBlockMissingCodeFence:
    """[NEW] headers with no balanced code fence must raise ParsingError."""

    def test_no_code_fence(self):
        """A [NEW] header with prose only must fail."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] .agent/src/agent/mod.py\n\n"
            "This is just prose.\n"
        )
        with pytest.raises(ParsingError, match="no balanced code fence"):
            _extract_runbook_data(content)

    def test_empty_code_fence(self):
        """A [NEW] header with empty fence must fail."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] .agent/src/agent/empty.py\n\n"
            "```python\n```\n"
        )
        with pytest.raises(ParsingError, match="no balanced code fence"):
            _extract_runbook_data(content)


# ── Empty S/R content in [MODIFY] tags (AC-3b) ───────────────


class TestModifyBlockEmptySearchReplace:
    """[MODIFY] with empty or missing S/R blocks must fail."""

    def test_no_search_replace(self):
        """A [MODIFY] with no SEARCH block must fail."""
        content = _wrap_runbook(
            "### Step 1: Update file\n\n"
            "#### [MODIFY] .agent/src/agent/commands/runbook.py\n\n"
            "Just prose.\n"
        )
        with pytest.raises(ParsingError, match="no valid SEARCH/REPLACE"):
            _extract_runbook_data(content)


# ── Malformed file paths (AC-3c) ─────────────────────────────


class TestMalformedFilePaths:
    """Traversal and absolute paths must be rejected."""

    def test_traversal_path(self):
        """Paths with '..' must fail validation."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] ../etc/passwd\n\n"
            "```python\n# bad\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert any("safe" in v.lower() or "relative" in v.lower() for v in violations)

    def test_absolute_path(self):
        """Absolute paths must fail validation."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] /tmp/exploit.py\n\n"
            "```python\n# bad\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert any("safe" in v.lower() or "relative" in v.lower() for v in violations)


# ── Missing header (AC-3d) ───────────────────────────────────


class TestMissingHeader:
    """Runbooks without the steps header must fail."""

    def test_no_header(self):
        """Missing steps section must produce violations."""
        content = "# Runbook\n\n## Overview\n\nText.\n"
        violations = validate_runbook_schema(content)
        assert len(violations) >= 1


# ── Python syntax validation (AC-1, AC-2) ─────────────────────


class TestPythonSyntaxValidation:
    """ast.parse() catches syntax errors in [NEW] .py blocks."""

    def test_valid_python_no_warnings(self):
        """Valid Python produces no warnings."""
        step_data = [{
            "title": "Create module",
            "operations": [{
                "path": "mod.py",
                "content": '"""Mod."""\n\ndef hi():\n    """Hi."""\n    return 1\n',
            }],
        }]
        assert _check_python_syntax(step_data) == []

    def test_syntax_error_detected(self):
        """SyntaxError produces a warning."""
        step_data = [{
            "title": "Create module",
            "operations": [{
                "path": "bad.py",
                "content": "def bad(\n    return 42\n",
            }],
        }]
        warnings = _check_python_syntax(step_data)
        assert len(warnings) == 1
        assert "syntax error" in warnings[0].lower()

    def test_non_python_skipped(self):
        """Non-.py files are skipped."""
        step_data = [{
            "title": "Config",
            "operations": [{"path": "config.yaml", "content": "bad: yaml:"}],
        }]
        assert _check_python_syntax(step_data) == []

    def test_modify_blocks_skipped(self):
        """MODIFY ops (no content key) are skipped."""
        step_data = [{
            "title": "Update",
            "operations": [{
                "path": "mod.py",
                "blocks": [{"search": "old", "replace": "new"}],
            }],
        }]
        assert _check_python_syntax(step_data) == []

    def test_warnings_are_nonblocking(self):
        """Syntax errors do NOT appear in violations."""
        content = _wrap_runbook(
            "### Step 1: Create broken module\n\n"
            "#### [NEW] .agent/src/agent/broken.py\n\n"
            "```python\ndef bad(\n    return 42\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert not any("syntax" in v.lower() for v in violations)


# ── Full pipeline ─────────────────────────────────────────────


class TestFullPipeline:
    """End-to-end validate_runbook_schema tests."""

    def test_valid_runbook(self):
        """Structurally valid runbook returns no violations."""
        content = _wrap_runbook(
            "### Step 1: Create helper\n\n"
            "#### [NEW] .agent/src/agent/helper.py\n\n"
            "```python\n"
            '"""Helper."""\n\n\n'
            "def greet():\n"
            '    """Greet."""\n'
            '    return "hi"\n'
            "```\n"
        )
        assert validate_runbook_schema(content) == []
```

## Verification Plan

### Automated Tests

```bash
cd .agent && uv run pytest src/agent/core/implement/tests/test_runbook_validation.py -v --tb=short
```

```bash
cd .agent && uv run pytest src/agent/core/implement/tests/ -v --tb=short
```

```bash
cd .agent && uv run pytest tests/ -v --tb=short
```

### Manual Verification

- Run `agent preflight` to confirm all governance checks pass

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added for syntax warning log events

### Testing

- [ ] All existing tests pass
- [ ] New tests in `test_runbook_validation.py` pass

## Copyright

Copyright 2026 Justin Cook
