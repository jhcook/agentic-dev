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

"""Unit + integration tests for INFRA-177: Gate 0 (projected LOC) and Gate 1b (malformed MODIFY)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.core.implement.loc_guard import check_projected_loc
from agent.core.implement.parser import detect_malformed_modify_blocks


# ---------------------------------------------------------------------------
# Helpers — build minimal runbook markdown fragments
# ---------------------------------------------------------------------------

def _new_block(file_path: str, content: str) -> str:
    """Minimal [NEW] runbook block. Content must end with \\n."""
    body = content if content.endswith("\n") else content + "\n"
    return (
        f"#### [NEW] {file_path}\n\n"
        "```python\n"
        f"{body}"
        "```\n"
    )


def _modify_block(file_path: str, search: str, replace: str) -> str:
    """Minimal [MODIFY] runbook block with S/R markers."""
    return (
        f"#### [MODIFY] {file_path}\n\n"
        "```python\n"
        f"<<<SEARCH\n{search}===\n{replace}>>>\n"
        "```\n"
    )


# ---------------------------------------------------------------------------
# AC-1: MODIFY block that would push file over limit → correction
# ---------------------------------------------------------------------------

def test_modify_exceeds_limit(tmp_path: Path) -> None:
    """MODIFY adds 20 lines to a 490-line file — projects to 510, blocked."""
    target = tmp_path / "oversized.py"
    target.write_text("line\n" * 490)

    content = _modify_block(
        "oversized.py",
        search="line\n",        # 1 line removed
        replace="line\n" * 21,  # 21 lines added → delta +20 → 510
    )

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        errors = check_projected_loc(content, tmp_path)

    assert len(errors) == 1
    assert "would reach 510 lines" in errors[0]
    assert "oversized.py" in errors[0]


# ---------------------------------------------------------------------------
# AC-2: NEW block whose content exceeds limit → correction
# ---------------------------------------------------------------------------

def test_new_block_exceeds_limit(tmp_path: Path) -> None:
    """NEW block with 520-line content is blocked."""
    block_content = "line\n" * 520  # 520 lines, trailing-newline terminated
    content = _new_block("brand_new.py", block_content)

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        errors = check_projected_loc(content, tmp_path)

    assert len(errors) == 1
    assert "would reach 520 lines" in errors[0]


# ---------------------------------------------------------------------------
# AC-3: Blocks within limit → clean pass
# ---------------------------------------------------------------------------

def test_modify_within_limit(tmp_path: Path) -> None:
    """MODIFY that adds 10 lines to a 470-line file passes cleanly."""
    target = tmp_path / "ok.py"
    target.write_text("line\n" * 470)

    content = _modify_block(
        "ok.py",
        search="line\n",
        replace="line\n" * 11,  # delta +10 → 480
    )

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(content, tmp_path) == []


def test_new_block_within_limit(tmp_path: Path) -> None:
    """NEW block with 50 lines passes cleanly."""
    content = _new_block("fresh.py", "line\n" * 50)

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(content, tmp_path) == []


# ---------------------------------------------------------------------------
# AC-4: Missing MODIFY target → no-op
# ---------------------------------------------------------------------------

def test_modify_missing_file_is_noop(tmp_path: Path) -> None:
    """MODIFY on a non-existent file is silently skipped (delegated to S/R gate)."""
    content = _modify_block("does_not_exist.py", "old\n", "new\n")

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(content, tmp_path) == []


# ---------------------------------------------------------------------------
# Negative delta (shrinking file) stays within limit → pass
# ---------------------------------------------------------------------------

def test_modify_negative_delta_passes(tmp_path: Path) -> None:
    """Shrinking a 550-line file by 90 lines projects to 460 — passes."""
    target = tmp_path / "shrinking.py"
    target.write_text("line\n" * 550)

    content = _modify_block(
        "shrinking.py",
        search="line\n" * 100,
        replace="line\n" * 10,  # delta -90 → 460
    )

    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(content, tmp_path) == []


# ---------------------------------------------------------------------------
# Empty content → no-op
# ---------------------------------------------------------------------------

def test_empty_content_noop(tmp_path: Path) -> None:
    """Empty runbook content returns no errors."""
    with patch("agent.core.implement.loc_guard.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc("", tmp_path) == []


# ---------------------------------------------------------------------------
# AC-6: Gate 1b — malformed [MODIFY] blocks (missing <<<SEARCH markers)
# ---------------------------------------------------------------------------

def test_detect_malformed_modify_clean() -> None:
    """Well-formed [MODIFY] with S/R markers is not flagged."""
    content = """
### Step 1

#### [MODIFY] foo/bar.py

```python
<<<SEARCH
old code
===
new code
>>>
```
"""
    assert detect_malformed_modify_blocks(content) == []


def test_detect_malformed_modify_missing_sr() -> None:
    """[MODIFY] with a bare fenced block (no <<<SEARCH) is detected."""
    content = """
### Step 1

#### [MODIFY] foo/bar.py

```python
def foo():
    pass
```
"""
    malformed = detect_malformed_modify_blocks(content)
    assert len(malformed) == 1
    assert "foo/bar.py" in malformed[0]


def test_detect_malformed_modify_multiple_files() -> None:
    """Two malformed [MODIFY] blocks — both are reported."""
    content = """
#### [MODIFY] alpha.py

```python
x = 1
```

#### [MODIFY] beta.py

```python
y = 2
```
"""
    malformed = detect_malformed_modify_blocks(content)
    assert len(malformed) == 2


# ---------------------------------------------------------------------------
# Integration: run_generation_gates wires Gate 0 into correction_parts
# ---------------------------------------------------------------------------

def _make_modify_runbook(file_path: str, search: str, replace: str) -> str:
    """Return minimal runbook markdown with one well-formed MODIFY S/R block."""
    return (
        "## State\n\nACCEPTED\n\n"
        "## Implementation Steps\n\n"
        "### Step 1\n\n"
        f"#### [MODIFY] {file_path}\n\n"
        "```python\n"
        f"<<<SEARCH\n{search}===\n{replace}>>>\n"
        "```\n"
    )


def test_run_generation_gates_loc_violation_in_correction_parts(tmp_path: Path) -> None:
    """Integration (AC-1 wiring): over-budget MODIFY → LOC warning in correction_parts."""
    from agent.commands.runbook_gates import run_generation_gates

    # 490-line file; adding 21 lines projects to 510 > 500 limit
    target = tmp_path / "bigfile.py"
    target.write_text("line\n" * 490)

    content = _make_modify_runbook(
        file_path="bigfile.py",
        search="line\n",          # 1 line removed
        replace="line\n" * 21,   # 21 lines added → delta +20
    )

    with (
        patch("agent.commands.runbook_gates.validate_runbook_schema", return_value=[]),
        patch(
            "agent.commands.runbook_gates.validate_code_block",
            return_value=MagicMock(errors=[], warnings=[]),
        ),
        patch("agent.commands.runbook_gates.validate_sr_blocks", return_value=[]),
        patch("agent.commands.runbook_gates.check_impact_analysis_completeness", return_value=[]),
        patch("agent.commands.runbook_gates.check_adr_refs", return_value=[]),
        patch("agent.commands.runbook_gates.check_stub_implementations", return_value=[]),
        # Patch config where each module reads it
        patch("agent.commands.runbook_gates.config") as gates_cfg,
        patch("agent.core.implement.loc_guard.config") as loc_cfg,
    ):
        gates_cfg.repo_root = tmp_path
        gates_cfg.max_correction_tokens = 10000
        loc_cfg.max_file_loc = 500

        _content, correction_parts, _gate_corr, _new_files, _delta = run_generation_gates(
            content=content,
            story_id="INFRA-177",
            story_content="Test story content",
            user_prompt="Generate runbook",
            system_prompt="System prompt",
            known_new_files=set(),
            attempt=1,
            max_attempts=5,
            gate_corrections=0,
            max_gate_corrections=3,
        )

    combined = "\n".join(correction_parts)
    assert correction_parts, "Expected at least one correction from Gate 0 LOC violation"
    assert "bigfile.py" in combined
    assert any(
        keyword in combined for keyword in ("LOC GATE", "would reach", "510 lines")
    ), f"Expected LOC gate violation text, got: {combined!r}"
