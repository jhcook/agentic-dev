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

"""Unit tests for INFRA-185 AC-11 pipeline hardening changes.

Covers:
- runbook_postprocess._autocorrect_schema_violations: empty MODIFY block removal
- parser.validate_runbook_schema: malformed block filtering before Pydantic validation
"""

import re
from typing import List

import pytest

from agent.commands.runbook_postprocess import _autocorrect_schema_violations
from agent.core.implement.parser import validate_runbook_schema


class TestAutocorrectEmptyModifyRemoval:
    """Tests for _autocorrect_schema_violations removing empty MODIFY blocks."""

    def test_empty_modify_block_stripped(self) -> None:
        """An empty MODIFY block (no <<<SEARCH) is replaced with a comment."""
        content = (
            "### Step 1: Fix configuration\n"
            "#### [MODIFY] agent/core/config.py\n"
            "Update the configuration handling.\n"
            "### Step 2: Next step\n"
        )
        result = _autocorrect_schema_violations(content)
        assert "schema-autocorrect: removed empty MODIFY block" in result
        assert "agent/core/config.py" in result
        assert "#### [MODIFY] agent/core/config.py" not in result

    def test_valid_modify_block_preserved(self) -> None:
        """A MODIFY block with valid <<<SEARCH content is NOT removed."""
        content = (
            "### Step 1: Fix configuration\n"
            "#### [MODIFY] agent/core/config.py\n"
            "```python\n"
            "<<<SEARCH\n"
            "old_code()\n"
            "===\n"
            "new_code()\n"
            ">>>\n"
            "```\n"
            "### Step 2: Next step\n"
        )
        result = _autocorrect_schema_violations(content)
        assert "#### [MODIFY] agent/core/config.py" in result
        assert "old_code()" in result
        assert "new_code()" in result


class TestParserMalformedBlockFiltering:
    """Tests for parser.validate_runbook_schema filtering malformed blocks."""

    RUNBOOK_TEMPLATE = (
        "## Implementation Steps\n\n"
        "### Step 1: {title}\n\n"
        "{operations}\n"
    )

    def _make_runbook(self, title: str, operations: str) -> str:
        """Build a minimal runbook for testing."""
        return self.RUNBOOK_TEMPLATE.format(title=title, operations=operations)

    def test_malformed_modify_reported_as_violation(self) -> None:
        """A MODIFY header with no S/R blocks is reported as a violation."""
        runbook = self._make_runbook(
            "Fix config",
            "#### [MODIFY] agent/core/config.py\n"
            "Update the configuration.\n",
        )
        violations: List[str] = validate_runbook_schema(runbook)
        modify_violations = [v for v in violations if "MODIFY" in v and "config.py" in v]
        assert len(modify_violations) > 0, f"Expected MODIFY violation for config.py, got: {violations}"

    def test_valid_modify_no_violation(self) -> None:
        """A MODIFY header with valid S/R blocks does not produce violations."""
        runbook = self._make_runbook(
            "Fix config",
            "#### [MODIFY] agent/core/config.py\n"
            "```python\n"
            "<<<SEARCH\n"
            "old_value = 1\n"
            "===\n"
            "new_value = 2\n"
            ">>>\n"
            "```\n",
        )
        violations: List[str] = validate_runbook_schema(runbook)
        modify_violations = [v for v in violations if "MODIFY" in v and "config.py" in v]
        assert len(modify_violations) == 0, f"Unexpected MODIFY violation: {modify_violations}"

    def test_malformed_new_reported_as_violation(self) -> None:
        """A NEW header with no code block content is reported as a violation."""
        runbook = self._make_runbook(
            "Add utility",
            "#### [NEW] agent/utils/helper.py\n"
            "This file provides helpers.\n",
        )
        violations: List[str] = validate_runbook_schema(runbook)
        new_violations = [v for v in violations if "NEW" in v and "helper.py" in v]
        assert len(new_violations) > 0, f"Expected NEW violation for helper.py, got: {violations}"
