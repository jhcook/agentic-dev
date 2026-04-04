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

import pytest
from pathlib import Path
from agent.commands.runbook_gates import run_generation_gates
from agent.core.config import config

# Use a variable so no literal triple-backtick appears in the runbook source,
# which would confuse the runbook parser's fence-extraction logic.
_FENCE = "` ``" .replace(" ", "")


def test_run_generation_gates_detects_bad_test_import(tmp_path):
    """Integration test: verify run_generation_gates returns a correction for unresolvable imports."""
    config.repo_root = tmp_path

    runbook_content = (
        "#### [NEW] tests/test_failure.py\n"
        "\n"
        f"{_FENCE}python\n"
        "from agent.missing_module import MissingClass\n"
        "\n"
        "def test_nothing():\n"
        "    pass\n"
        "\n"
        f"{_FENCE}\n"
    )
    _, correction_parts, _, _, _ = run_generation_gates(
        content=runbook_content,
        story_id="INFRA-178",
        story_content="Sample story",
        user_prompt="implement the fix",
        system_prompt="you are an agent",
        known_new_files=set(),
        attempt=1,
        max_attempts=3,
        gate_corrections=0,
        max_gate_corrections=5,
    )

    assert any("IMPORT RESOLUTION FAILURE" in p for p in correction_parts)
    assert any("agent.missing_module.MissingClass" in p for p in correction_parts)


def test_run_generation_gates_passes_with_cross_block_dependency(tmp_path):
    """Integration test: verify a test importing a symbol defined in the same runbook passes."""
    config.repo_root = tmp_path

    runbook_content = (
        "#### [NEW] agent/core/logic.py\n"
        "\n"
        f"{_FENCE}python\n"
        "class NewLogic:\n"
        "    def execute(self):\n"
        "        return True\n"
        "\n"
        f"{_FENCE}\n"
        "\n"
        "#### [NEW] tests/test_logic.py\n"
        "\n"
        f"{_FENCE}python\n"
        "from agent.core.logic import NewLogic\n"
        "\n"
        "def test_new_logic():\n"
        "    assert NewLogic().execute()\n"
        "\n"
        f"{_FENCE}\n"
    )
    _, correction_parts, _, _, _ = run_generation_gates(
        content=runbook_content,
        story_id="INFRA-178",
        story_content="Sample story",
        user_prompt="implement logic and test",
        system_prompt="agent",
        known_new_files=set(),
        attempt=1,
        max_attempts=3,
        gate_corrections=0,
        max_gate_corrections=5,
    )

    import_failures = [p for p in correction_parts if "IMPORT RESOLUTION FAILURE" in p]
    assert not import_failures, f"Expected no import failures, got: {import_failures}"
