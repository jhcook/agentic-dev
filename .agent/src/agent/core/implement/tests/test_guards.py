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

"""
Unit tests for DoD Compliance Gate verifiers (INFRA-162).

Tests for check_impact_analysis_completeness and check_adr_refs in guards.py.
"""

from pathlib import Path
import pytest
from agent.core.implement.guards import (
    check_impact_analysis_completeness,
    check_adr_refs,
    check_op_type_vs_filesystem,
    check_stub_implementations,
)


def test_impact_analysis_completeness_happy_path():
    """
    Verify that correctly documented files pass validation.
    """
    content = """
#### [MODIFY] agent/core/utils.py
#### [NEW] agent/core/new_feature.py
#### [DELETE] agent/old_file.py

Step N: Update Impact Analysis in story file
**Components touched:**
- `agent/core/utils.py` — **MODIFIED**
- `agent/core/new_feature.py` — **NEW**
- `agent/old_file.py` — **DELETED**
"""
    errors = check_impact_analysis_completeness(content)
    assert not errors


def test_impact_analysis_completeness_missing_file():
    """
    Verify that missing files in Step N trigger an error.
    """
    content = """
#### [MODIFY] agent/core/utils.py
#### [NEW] agent/core/new_feature.py

Step N: Update Impact Analysis in story file
**Components touched:**
- `agent/core/utils.py` — **MODIFIED**
"""
    errors = check_impact_analysis_completeness(content)
    assert len(errors) == 1
    assert "agent/core/new_feature.py" in errors[0]


def test_impact_analysis_completeness_excludes_housekeeping():
    """
    Verify that CHANGELOG.md and story files are exempt from Impact Analysis checks.
    """
    content = """
#### [MODIFY] CHANGELOG.md
#### [MODIFY] .agent/cache/stories/INFRA/INFRA-123.md

Step N: Update Impact Analysis in story file
**Components touched:**
"""
    errors = check_impact_analysis_completeness(content)
    assert not errors


def test_adr_refs_happy_path(tmp_path):
    """
    Verify that existing ADRs pass validation.
    """
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-005-governance.md").write_text("...")
    (adr_dir / "ADR-040-loop.md").write_text("...")

    content = "This follows ADR-005 and ADR-040."
    errors = check_adr_refs(content, adr_dir)
    assert not errors


def test_adr_refs_hallucinated(tmp_path):
    """
    Verify that non-existent ADRs trigger an error.
    """
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-005-governance.md").write_text("...")

    content = "This follows ADR-005 and ADR-999."
    errors = check_adr_refs(content, adr_dir)
    assert len(errors) == 1
    assert "ADR-999" in errors[0]


def test_adr_refs_missing_dir(tmp_path):
    """
    Verify graceful handling of missing ADR directory.
    """
    adr_dir = tmp_path / "non_existent"
    content = "Referencing ADR-005."
    errors = check_adr_refs(content, adr_dir)
    assert len(errors) == 1
    assert "ADR directory not found" in errors[0]


def test_adr_refs_empty_content(tmp_path):
    """
    Verify that empty content or content with no ADRs passes.
    """
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    assert not check_adr_refs("", adr_dir)
    assert not check_adr_refs("Just some text.", adr_dir)


# ---------------------------------------------------------------------------
# check_op_type_vs_filesystem
# ---------------------------------------------------------------------------

def test_op_type_modify_existing_file_passes(tmp_path):
    """
    Verify that [MODIFY] on a file that exists on disk passes.
    """
    existing = tmp_path / "agent" / "core" / "utils.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("# existing")

    content = "#### [MODIFY] agent/core/utils.py"
    errors = check_op_type_vs_filesystem(content, tmp_path)
    assert not errors


def test_op_type_modify_missing_file_fails(tmp_path):
    """
    Verify that [MODIFY] on a non-existent file triggers an error.
    """
    content = "#### [MODIFY] agent/commands/preflight.py"
    errors = check_op_type_vs_filesystem(content, tmp_path)
    assert len(errors) == 1
    assert "preflight.py" in errors[0]
    assert "[NEW]" in errors[0]


def test_op_type_new_never_checked(tmp_path):
    """
    Verify that [NEW] paths are not checked (new files won't exist yet).
    """
    content = "#### [NEW] agent/commands/preflight.py"
    errors = check_op_type_vs_filesystem(content, tmp_path)
    assert not errors


def test_op_type_exempts_changelog_and_cache(tmp_path):
    """
    Verify CHANGELOG.md and .agent/cache/ paths are exempt.
    """
    content = (
        "#### [MODIFY] CHANGELOG.md\n"
        "#### [MODIFY] .agent/cache/stories/INFRA/INFRA-123.md\n"
    )
    errors = check_op_type_vs_filesystem(content, tmp_path)
    assert not errors


# ---------------------------------------------------------------------------
# check_stub_implementations
# ---------------------------------------------------------------------------

def _wrap(code: str) -> str:
    """Wrap code in a fenced block as a runbook would."""
    return f"```python\n{code}\n```"


def test_stub_pass_body_detected():
    content = _wrap("def heal():\n    pass")
    errors = check_stub_implementations(content)
    assert len(errors) >= 1
    assert "pass" in errors[0]


def test_stub_not_implemented_detected():
    content = _wrap("def heal():\n    raise NotImplementedError")
    errors = check_stub_implementations(content)
    assert any("NotImplementedError" in e for e in errors)


def test_stub_todo_comment_detected():
    content = _wrap("def heal():\n    # TODO: add real logic\n    return True")
    errors = check_stub_implementations(content)
    assert any("TODO" in e for e in errors)


def test_stub_placeholder_comment_detected():
    content = _wrap("def heal():\n    # Orchestrate AI fix logic here...\n    return True")
    errors = check_stub_implementations(content)
    assert len(errors) >= 1


def test_stub_clean_implementation_passes():
    content = _wrap(
        "def heal(role, findings):\n"
        "    result = ai_service.complete(role, findings)\n"
        "    return bool(result)\n"
    )
    errors = check_stub_implementations(content)
    assert not errors


def test_stub_no_code_blocks_passes():
    content = "## Some prose\n\nNo code here."
    errors = check_stub_implementations(content)
    assert not errors
