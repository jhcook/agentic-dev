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

"""Tests for INFRA-136 scope guardrails and approved file extraction."""

import pytest

from agent.core.implement.parser import (
    extract_approved_files,
    extract_cross_cutting_files,
)
from agent.core.implement.orchestrator import Orchestrator


SAMPLE_RUNBOOK = (
    "## Implementation Steps\n\n"
    "### Step 1: Modify config\n\n"
    "[MODIFY] .agent/src/agent/core/config.py\n\n"
    "```\n<<<SEARCH\nold\n===\nnew\n>>>\n```\n\n"
    "### Step 2: Create helper\n\n"
    "[NEW] .agent/src/agent/core/helper.py\n\n"
    '```python\n"""Helper."""\ndef helper():\n    """Help."""\n    pass\n```\n\n'
    "### Step 3: Remove legacy\n\n"
    "[DELETE] .agent/src/agent/core/old.py\n\n"
    "<!-- Replaced by helper.py -->\n"
)

CROSS_CUTTING_RUNBOOK = (
    "## Implementation Steps\n\n"
    "### Step 1: Update shared util\n\n"
    "<!-- cross_cutting: true -->\n"
    "#### [MODIFY] .agent/src/agent/core/utils.py\n\n"
    "```\n<<<SEARCH\nold\n===\nnew\n>>>\n```\n"
)


class TestExtractApprovedFiles:
    """Tests for extract_approved_files() — AC-2."""

    def test_extracts_all_block_types(self):
        """Captures MODIFY, NEW, and DELETE paths."""
        approved = extract_approved_files(SAMPLE_RUNBOOK)
        assert ".agent/src/agent/core/config.py" in approved
        assert ".agent/src/agent/core/helper.py" in approved
        assert ".agent/src/agent/core/old.py" in approved
        assert len(approved) == 3

    def test_empty_runbook(self):
        """Empty content returns empty set."""
        assert extract_approved_files("") == set()


class TestExtractCrossCuttingFiles:
    """Tests for extract_cross_cutting_files() — AC-4."""

    def test_extracts_annotated_file(self):
        """Captures file with cross_cutting annotation before header."""
        cc = extract_cross_cutting_files(CROSS_CUTTING_RUNBOOK)
        assert ".agent/src/agent/core/utils.py" in cc

    def test_not_cross_cutting_without_annotation(self):
        """Files without annotation are not cross_cutting."""
        cc = extract_cross_cutting_files(SAMPLE_RUNBOOK)
        assert len(cc) == 0


class TestScopeGuard:
    """Tests for Orchestrator._check_scope() — AC-2, AC-5."""

    def test_approved_file_allowed(self):
        """File in approved set passes scope check."""
        orch = Orchestrator(
            "TEST-001", approved_files={".agent/src/agent/core/config.py"},
        )
        assert orch._check_scope(".agent/src/agent/core/config.py", 1) is True
        assert orch.scope_violations == 0

    def test_unapproved_file_blocked(self):
        """File not in approved set is scope-violated."""
        orch = Orchestrator(
            "TEST-001", approved_files={".agent/src/agent/core/config.py"},
        )
        result = orch._check_scope(".agent/src/agent/core/rogue.py", 1)
        assert result is False
        assert orch.scope_violations == 1
        assert ".agent/src/agent/core/rogue.py" in orch.rejected_files

    def test_cross_cutting_bypasses_scope(self):
        """File in cross_cutting set bypasses scope check."""
        orch = Orchestrator(
            "TEST-001",
            approved_files={".agent/src/agent/core/config.py"},
            cross_cutting_files={".agent/src/agent/core/utils.py"},
        )
        assert orch._check_scope(".agent/src/agent/core/utils.py", 1) is True
        assert orch.scope_violations == 0

    def test_no_approved_set_allows_all(self):
        """When approved_files is None, scope is not enforced."""
        orch = Orchestrator("TEST-001")
        assert orch._check_scope("any/file.py", 1) is True


class TestHallucinationRate:
    """Tests for hallucination rate scoring — AC-3."""

    def test_zero_blocks_returns_zero(self):
        """No blocks -> 0.0 rate."""
        orch = Orchestrator("TEST-001")
        assert orch.get_hallucination_rate() == 0.0

    def test_rate_computed_correctly(self):
        """Rate = violations / total."""
        orch = Orchestrator("TEST-001")
        orch.total_blocks = 10
        orch.scope_violations = 3
        assert orch.get_hallucination_rate() == pytest.approx(0.3)