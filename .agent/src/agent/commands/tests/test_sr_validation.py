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

"""Unit and integration tests for INFRA-159 S/R block validation helpers.

Tests:
- _lines_match: whitespace normalisation, empty block, exact match
- validate_sr_blocks: happy path, mismatch, new-file exempt, missing MODIFY target
- generate_sr_correction_prompt: structure, scrub_sensitive_data applied
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from agent.commands.utils import (
    _lines_match,
    validate_sr_blocks,
    generate_sr_correction_prompt,
)


# ---------------------------------------------------------------------------
# _lines_match
# ---------------------------------------------------------------------------

PYTHON_FILE = """\
def foo():
    return 1


def bar():
    return 2
"""


class TestLinesMatch:
    """Unit tests for _lines_match."""

    def test_exact_match(self):
        """Search block found verbatim in file content."""
        assert _lines_match("def foo():\n    return 1", PYTHON_FILE)

    def test_trailing_whitespace_ignored(self):
        """Trailing spaces on each line do not cause a mismatch."""
        search = "def foo():   \n    return 1   "
        assert _lines_match(search, PYTHON_FILE)

    def test_no_match(self):
        """Search block absent from file — returns False."""
        assert not _lines_match("def baz():\n    return 99", PYTHON_FILE)

    def test_empty_search_always_matches(self):
        """Empty search string is treated as an unconditional match."""
        assert _lines_match("", PYTHON_FILE)

    def test_single_line_match(self):
        """Single-line search block works correctly."""
        assert _lines_match("def bar():", PYTHON_FILE)

    def test_search_longer_than_file(self):
        """Block longer than the file cannot match."""
        long_block = "\n".join(["line"] * 1000)
        assert not _lines_match(long_block, "line\n")


# ---------------------------------------------------------------------------
# Runbook fixtures
# ---------------------------------------------------------------------------

RUNBOOK_MODIFY_MATCH = """\
## Implementation Steps

### Step 1: Update foo

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
def foo():
    return 1
===
def foo():
    return 42
>>>
```
"""

RUNBOOK_MODIFY_MISMATCH = """\
## Implementation Steps

### Step 1: Update foo

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
def foo():
    return 99
===
def foo():
    return 42
>>>
```
"""

RUNBOOK_NEW_FILE = """\
## Implementation Steps

### Step 1: Create helper

#### [NEW] .agent/src/agent/commands/new_helper.py

```python
def helper():
    pass
```
"""

RUNBOOK_MISSING_MODIFY_TARGET = """\
## Implementation Steps

### Step 1: Modify nonexistent

#### [MODIFY] .agent/src/nonexistent_module.py

```
<<<SEARCH
some content
===
new content
>>>
```
"""

RUNBOOK_TWO_BLOCKS_SAME_FILE = """\
## Implementation Steps

### Step 1: Two blocks

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
def foo():
    return 1
===
def foo():
    return 42
>>>
```

```
<<<SEARCH
def bar():
    return 2
===
def bar():
    return 99
>>>
```
"""


# ---------------------------------------------------------------------------
# validate_sr_blocks
# ---------------------------------------------------------------------------

class TestValidateSrBlocks:
    """Unit tests for validate_sr_blocks."""

    def _make_target(self, tmp_path: Path, rel: str, content: str) -> Path:
        """Write *content* to a file at *rel* relative to repo root mock."""
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def test_all_blocks_match(self, tmp_path):
        """No mismatches when SEARCH content exists verbatim in the target."""
        target_content = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        target = self._make_target(tmp_path, "agent/commands/utils.py", target_content)

        with patch("agent.core.implement.resolver.resolve_path", return_value=target):
            result = validate_sr_blocks(RUNBOOK_MODIFY_MATCH)

        assert result == []

    def test_mismatch_detected(self, tmp_path):
        """Mismatch returns one entry with correct file path and block index."""
        target_content = "def foo():\n    return 1\n"
        target = self._make_target(tmp_path, "agent/commands/utils.py", target_content)

        with patch("agent.core.implement.resolver.resolve_path", return_value=target):
            result = validate_sr_blocks(RUNBOOK_MODIFY_MISMATCH)

        assert len(result) == 1
        assert result[0]["file"].endswith("utils.py")
        assert result[0]["index"] == 1
        assert "return 99" in result[0]["search"]
        assert "return 1" in result[0]["actual"]

    def test_new_file_exempt(self, tmp_path):
        """[NEW] blocks whose target doesn't exist yet are skipped."""
        # resolve_path returns a path that doesn't exist → no file to match
        nonexistent = tmp_path / "agent/commands/new_helper.py"

        with patch("agent.core.implement.resolver.resolve_path", return_value=nonexistent):
            result = validate_sr_blocks(RUNBOOK_NEW_FILE)

        assert result == []

    def test_missing_modify_target_raises(self, tmp_path):
        """[MODIFY] block targeting a missing file raises FileNotFoundError immediately."""
        nonexistent = tmp_path / "agent/src/nonexistent_module.py"

        with patch("agent.core.implement.resolver.resolve_path", return_value=nonexistent):
            with pytest.raises(FileNotFoundError, match="nonexistent_module"):
                validate_sr_blocks(RUNBOOK_MISSING_MODIFY_TARGET)

    def test_two_blocks_same_file_indexed(self, tmp_path):
        """Multiple blocks against the same file get sequential 1-based indices."""
        target_content = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        target = self._make_target(tmp_path, "agent/commands/utils.py", target_content)

        with patch("agent.core.implement.resolver.resolve_path", return_value=target):
            result = validate_sr_blocks(RUNBOOK_TWO_BLOCKS_SAME_FILE)

        # Both blocks match — no mismatches.
        assert result == []

    def test_two_blocks_first_mismatch(self, tmp_path):
        """First block mismatches, second matches — only first is reported."""
        # Only "def bar" exists, not "def foo: return 99"
        target_content = "def bar():\n    return 2\n"
        target = self._make_target(tmp_path, "agent/commands/utils.py", target_content)

        runbook = """\
## Implementation Steps

### Step 1: Two blocks

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
def foo():
    return 99
===
def foo():
    return 1
>>>
```

```
<<<SEARCH
def bar():
    return 2
===
def bar():
    return 99
>>>
```
"""
        with patch("agent.core.implement.resolver.resolve_path", return_value=target):
            result = validate_sr_blocks(runbook)

        assert len(result) == 1
        assert result[0]["index"] == 1


# ---------------------------------------------------------------------------
# generate_sr_correction_prompt
# ---------------------------------------------------------------------------

SAMPLE_MISMATCH = [
    {
        "file": "agent/commands/utils.py",
        "search": "def foo():\n    return 99",
        "actual": "def foo():\n    return 1\n",
        "index": 1,
    }
]


class TestGenerateSrCorrectionPrompt:
    """Unit tests for generate_sr_correction_prompt."""

    def test_contains_file_and_block_ref(self):
        """Prompt includes file path and block index."""
        prompt = generate_sr_correction_prompt(SAMPLE_MISMATCH)
        assert "agent/commands/utils.py" in prompt
        assert "Block #1" in prompt

    def test_contains_failing_search(self):
        """Prompt includes the failing SEARCH content."""
        prompt = generate_sr_correction_prompt(SAMPLE_MISMATCH)
        assert "return 99" in prompt

    def test_scrub_sensitive_data_applied(self):
        """scrub_sensitive_data is called on file content before embedding in prompt."""
        with patch("agent.commands.utils.scrub_sensitive_data", side_effect=lambda x: x) as mock_scrub:
            generate_sr_correction_prompt(SAMPLE_MISMATCH)

        # scrub_sensitive_data must have been called with the actual file content
        mock_scrub.assert_called_once_with("def foo():\n    return 1\n")

    def test_contains_instruction(self):
        """Prompt ends with a rewrite instruction."""
        prompt = generate_sr_correction_prompt(SAMPLE_MISMATCH)
        assert "Instruction:" in prompt
        assert "<<<SEARCH" in prompt

    def test_multiple_mismatches(self):
        """All mismatches are included in the prompt."""
        mismatches = [
            {"file": "a.py", "search": "x", "actual": "y", "index": 1},
            {"file": "b.py", "search": "p", "actual": "q", "index": 2},
        ]
        prompt = generate_sr_correction_prompt(mismatches)
        assert "a.py" in prompt
        assert "b.py" in prompt
        assert "Block #1" in prompt
        assert "Block #2" in prompt
