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

"""Unit tests for sr_validation module (INFRA-168).

Covers:
  - validate_and_correct_sr_blocks: exact match, fuzzy correct, below-threshold
  - fuzzy_find_and_replace: match found, no match, empty input
"""

import textwrap
from pathlib import Path

import pytest

from agent.core.implement.sr_validation import (
    fuzzy_find_and_replace,
    validate_and_correct_sr_blocks,
)


# ---------------------------------------------------------------------------
# validate_and_correct_sr_blocks
# ---------------------------------------------------------------------------


def test_validate_exact_match(tmp_path: Path):
    """No corrections when SEARCH text matches the file exactly."""
    target = tmp_path / "app.py"
    target.write_text("def hello():\n    return 'hi'\n")

    runbook = textwrap.dedent(f"""\
        #### [MODIFY] `{target}`
        <<<SEARCH
        def hello():
            return 'hi'
        ===
        def hello():
            return 'hello'
        >>>
    """)

    corrected, total, fixed = validate_and_correct_sr_blocks(runbook, repo_root=tmp_path)
    assert total == 1
    assert fixed == 0
    assert corrected == runbook  # unchanged


def test_validate_fuzzy_correction(tmp_path: Path):
    """Auto-corrects a hallucinated SEARCH block when fuzzy match passes threshold."""
    target = tmp_path / "app.py"
    target.write_text("def greet(name):\n    return f'Hello {name}'\n")

    # Hallucinated SEARCH — slightly wrong
    runbook = textwrap.dedent(f"""\
        #### [MODIFY] `{target}`
        <<<SEARCH
        def greet(name):
            return f'Hi {{name}}'
        ===
        def greet(name):
            return f'Goodbye {{name}}'
        >>>
    """)

    corrected, total, fixed = validate_and_correct_sr_blocks(
        runbook, repo_root=tmp_path, threshold=0.5
    )
    assert total == 1
    assert fixed == 1
    # The corrected content should contain the actual file text
    assert "Hello {name}" in corrected


def test_validate_below_threshold(tmp_path: Path):
    """Does not correct when best match is below threshold and AI re-anchor fails."""
    target = tmp_path / "app.py"
    target.write_text("completely different content\nnothing matches\n")

    runbook = textwrap.dedent(f"""\
        #### [MODIFY] `{target}`
        <<<SEARCH
        def totally_unrelated():
            pass
        ===
        def replacement():
            pass
        >>>
    """)

    from unittest.mock import patch

    with patch(
        "agent.core.implement.sr_validation._ai_reanchor_search", return_value=None
    ):
        corrected, total, fixed = validate_and_correct_sr_blocks(
            runbook, repo_root=tmp_path, threshold=0.9
        )
    assert total == 1
    assert fixed == 0  # below threshold, AI also failed


def test_validate_ai_reanchor(tmp_path: Path):
    """AI re-anchoring fixes a block that fuzzy matching cannot."""
    target = tmp_path / "app.py"
    actual = "def greet(name):\n    return f'Hello {name}'\n"
    target.write_text(actual)

    runbook = textwrap.dedent(f"""\
        #### [MODIFY] `{target}`
        <<<SEARCH
        something completely wrong
        ===
        def greet(name):
            return f'Goodbye {{name}}'
        >>>
    """)

    from unittest.mock import patch

    # Simulate AI returning the correct region
    with patch(
        "agent.core.implement.sr_validation._ai_reanchor_search",
        return_value="def greet(name):\n    return f'Hello {name}'",
    ):
        corrected, total, fixed = validate_and_correct_sr_blocks(
            runbook, repo_root=tmp_path, threshold=0.9
        )
    assert total == 1
    assert fixed == 1
    assert "Hello {name}" in corrected


def test_validate_missing_file(tmp_path: Path):
    """Skips validation for files that don't exist (NEW files)."""
    runbook = textwrap.dedent("""\
        #### [NEW] `nonexistent.py`
        ```python
        print("new file")
        ```
    """)

    corrected, total, fixed = validate_and_correct_sr_blocks(
        runbook, repo_root=tmp_path
    )
    assert total == 0
    assert fixed == 0


# ---------------------------------------------------------------------------
# fuzzy_find_and_replace
# ---------------------------------------------------------------------------


def test_fuzzy_match_found():
    """Applies replacement when a good fuzzy match exists."""
    content = "line one\ndef hello():\n    return 1\nline four\n"
    search = "def hello():\n    return 2"  # slightly wrong
    replace = "def hello():\n    return 42"

    result = fuzzy_find_and_replace(
        content, search, replace, "test.py", 1, 1, threshold=0.5
    )
    assert result is not None
    assert "return 42" in result
    assert "return 1" not in result


def test_fuzzy_no_match():
    """Returns None when no region meets the threshold."""
    content = "completely unrelated content\n"
    search = "def something_else():\n    pass"
    replace = "def replacement():\n    pass"

    result = fuzzy_find_and_replace(
        content, search, replace, "test.py", 1, 1, threshold=0.9
    )
    assert result is None


def test_fuzzy_empty_input():
    """Returns None for empty content or search."""
    assert fuzzy_find_and_replace("", "search", "replace", "f.py", 1, 1) is None
    assert fuzzy_find_and_replace("content", "", "replace", "f.py", 1, 1) is None
