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
    """[NEW] headers with no code block must be flagged malformed."""

    def test_no_code_fence(self):
        """A [NEW] header with prose only must be flagged malformed."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] .agent/src/agent/mod.py\n\n"
            "This is just prose.\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op.get("malformed") is True

    def test_empty_code_fence(self):
        """A [NEW] header with empty fence must be flagged malformed."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] .agent/src/agent/empty.py\n\n"
            "```python\n```\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op.get("malformed") is True


# ── Empty S/R content in [MODIFY] tags (AC-3b) ───────────────


class TestModifyBlockEmptySearchReplace:
    """[MODIFY] with empty or missing S/R blocks must be flagged malformed."""

    def test_no_search_replace(self):
        """A [MODIFY] with no SEARCH block must be flagged malformed."""
        content = _wrap_runbook(
            "### Step 1: Update file\n\n"
            "#### [MODIFY] .agent/src/agent/commands/runbook.py\n\n"
            "Just prose.\n"
        )
        steps = _extract_runbook_data(content)
        assert len(steps) == 1
        op = steps[0]["operations"][0]
        assert op.get("malformed") is True


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
        assert any("security" in v.lower() or "traversal" in v.lower() for v in violations)

    def test_absolute_path(self):
        """Absolute paths must fail validation."""
        content = _wrap_runbook(
            "### Step 1: Create file\n\n"
            "#### [NEW] /tmp/exploit.py\n\n"
            "```python\n# bad\n```\n"
        )
        violations = validate_runbook_schema(content)
        assert any("security" in v.lower() or "traversal" in v.lower() for v in violations)


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