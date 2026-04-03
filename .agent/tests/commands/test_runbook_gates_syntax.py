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

"""Integration tests: Gate 3.5 projected syntax validation pipeline.

These tests verify that ``run_generation_gates`` correctly wires Gate 3.5 into
the ``correction_parts`` list, as required by the story Test Strategy.

Unit-level tests for the ``check_projected_syntax`` function itself live in
``tests/unit/test_guards_syntax.py``.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch


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


def test_gate35_syntax_violation_appears_in_correction_parts(tmp_path: Path) -> None:
    """AC-6 wiring: syntactically invalid REPLACE → Gate 3.5 message in correction_parts.

    This test exercises the full run_generation_gates pipeline to verify that
    Gate 3.5 is correctly wired into the correction loop.
    """
    from agent.commands.runbook_gates import run_generation_gates

    target = tmp_path / "syntax_target.py"
    target.write_text("x = 1\n", encoding="utf-8")

    # trailing \n keeps >>> on its own line; unclosed paren = SyntaxError
    content = _make_modify_runbook(
        file_path="syntax_target.py",
        search="x = 1\n",
        replace="x = (\n",
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
        patch("agent.commands.runbook_gates.config") as gates_cfg,
        patch("agent.core.implement.loc_guard.config") as loc_cfg,
    ):
        gates_cfg.repo_root = tmp_path
        gates_cfg.max_correction_tokens = 10000
        loc_cfg.max_file_loc = 500

        _content, correction_parts, _gate_corr, _new_files, _delta = run_generation_gates(
            content=content,
            story_id="INFRA-176",
            story_content="Test story",
            user_prompt="Generate runbook",
            system_prompt="System prompt",
            known_new_files=set(),
            attempt=1,
            max_attempts=5,
            gate_corrections=0,
            max_gate_corrections=3,
        )

    combined = "\n".join(correction_parts)
    assert correction_parts, "Expected at least one correction from Gate 3.5 syntax violation"
    assert "Gate 3.5" in combined, f"Expected Gate 3.5 correction, got: {combined!r}"
    assert "syntax_target.py" in combined
