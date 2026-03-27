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

"""Tests for panel --apply Implementation Steps preservation.

Verifies that the panel apply flow validates runbook schema and that
a well-formed AI response preserving Implementation Steps passes
validation, while a malformed one (missing steps) is rejected.
"""

import re

import pytest

from agent.core.implement.parser import validate_runbook_schema


# ── Fixtures ─────────────────────────────────────────────────


IMPL_STEPS_SECTION = """\
## Implementation Steps

### Step 1: Create Tool Registry Foundation

#### [NEW] .agent/src/agent/tools/__init__.py

```python
# Copyright 2026 Justin Cook
\"\"\"Core tool registry.\"\"\"

from typing import Dict


class ToolRegistry:
    \"\"\"Central registry for managing agent tools.\"\"\"

    def __init__(self) -> None:
        \"\"\"Initialize the registry with an empty tool map.\"\"\"
        self._tools: Dict[str, object] = {}
```

### Step 2: Create test file

#### [NEW] .agent/src/agent/tools/tests/__init__.py

```python
\"\"\"Tests for the agent tools package.\"\"\"
```
"""

FULL_RUNBOOK = """\
# STORY-ID: INFRA-139: Core Tool Registry and Foundation

## State

ACCEPTED

## Goal Description

Establishes the centralized ToolRegistry.

## Panel Review Findings

### @Architect
- Validated dictionary-backed store for O(1) lookup.

""" + IMPL_STEPS_SECTION + """
## Verification Plan

### Automated Tests

- [ ] Run tests

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated

## Copyright

Copyright 2026 Justin Cook
"""


# ── Implementation Steps Preservation ────────────────────────


class TestImplementationStepsPreservation:
    """Verify the Implementation Steps section is validated correctly after panel apply."""

    def test_preserved_impl_steps_pass_validation(self):
        """A runbook whose Implementation Steps are character-for-character intact must pass."""
        violations = validate_runbook_schema(FULL_RUNBOOK)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_impl_steps_section_extracted_correctly(self):
        """The Implementation Steps section can be found and round-trips through validation."""
        # Extract the Implementation Steps section
        match = re.search(
            r'^(## Implementation Steps\s*\n.*)',
            FULL_RUNBOOK,
            re.DOTALL | re.MULTILINE,
        )
        assert match is not None, "Implementation Steps section not found"

        # Verify the section contains expected markers
        section = match.group(1)
        assert "#### [NEW]" in section
        assert "### Step 1:" in section
        assert "### Step 2:" in section

    def test_missing_impl_steps_fails_validation(self):
        """A runbook where AI strips the Implementation Steps section must fail."""
        stripped = FULL_RUNBOOK.replace(IMPL_STEPS_SECTION, "## Implementation Steps\n\n")
        violations = validate_runbook_schema(stripped)
        assert len(violations) >= 1, "Expected at least one violation for empty steps"

    def test_reformatted_markers_fail_validation(self):
        """Reformatted [NEW] markers (e.g. '#### New File:') are not parseable as
        file operations.  Under the relaxed schema (operations is optional), this
        no longer causes a *schema* violation — prose-only steps are intentionally
        valid.  However extract_modify_files MUST return an empty list, confirming
        that the markers were not silently accepted as file ops."""
        from agent.core.implement.parser import extract_modify_files
        broken = FULL_RUNBOOK.replace("#### [NEW]", "#### New File:")
        # Schema should now pass (prose-only steps are valid)
        violations = validate_runbook_schema(broken)
        assert violations == [], f"Unexpected schema violations: {violations}"
        # But no file paths must be extractable — the markers were lost
        files = extract_modify_files(broken)
        assert files == [], (
            f"Expected no extractable files when [NEW] markers are stripped, got {files}"
        )


    def test_truncated_code_blocks_fail_validation(self):
        """A runbook where AI truncates code blocks to empty must fail validation."""
        broken = re.sub(
            r'```python\n.*?```',
            '```python\n```',
            FULL_RUNBOOK,
            flags=re.DOTALL,
        )
        violations = validate_runbook_schema(broken)
        assert len(violations) >= 1, "Expected validation failure when code blocks are truncated"

    def test_panel_advice_in_review_section_passes(self):
        """Panel advice integrated into review sections (not Implementation Steps) passes."""
        updated = FULL_RUNBOOK.replace(
            "### @Architect\n- Validated dictionary-backed store for O(1) lookup.",
            "### @Architect\n- Validated dictionary-backed store for O(1) lookup.\n"
            "- **Advice Applied**: An ADR must be created for the design.",
        )
        violations = validate_runbook_schema(updated)
        assert violations == [], f"Expected no violations, got: {violations}"
