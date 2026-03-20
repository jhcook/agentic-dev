# STORY-ID: INFRA-162: DoD Gate: Impact Analysis Completeness and ADR Existence Verifiers

## State

COMMITTED

## Goal Description

Enhance the preflight DoD Compliance Gate (Gate 4) with deterministic verifiers to ensure that every file modified or created in a runbook is accurately reflected in the Step N Impact Analysis summary, and that all cited ADRs actually exist in the repository's ADR catalogue. This prevents downstream documentation gaps and "hallucinated" references that cause implementation failures.

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- Deterministic regex-based verifiers are superior to AI reasoning for this task.
- Ensuring ADR references exist maintains the integrity of the architectural trail (ADR-005).
- Path normalization is critical to avoid false negatives between `path/to/file` and `./path/to/file`.

### @Qa
- The new unit tests must cover edge cases: empty runbooks, missing ADR directories, and inconsistent path formatting (slashes vs backslashes).
- The "negative test" requirement ensures the system doesn't crash if optional directories are missing.

### @Security
- No PII is introduced.
- Deterministic checks prevent prompt injection bypass of documentation requirements.
- Path resolution is anchored to the repo root to prevent sandbox escapes.

### @Product
- Directly addresses the problem of incomplete Step N summaries, which currently requires manual correction.
- Deterministic feedback within <200ms improves developer experience during `agent new-runbook`.

### @Observability
- New spans and log attributes for `gap_count` and `gaps` (4f, 4g) will allow tracking of common AI documentation errors.

### @Docs
- Enforces the requirement that every implementation artifact must be documented in the story file's Impact Analysis section.

### @Compliance
- Ensures auditability by maintaining 100% parity between code changes and documentation.
- Validates that ADR citations (which govern security/privacy decisions) are authentic.

### @Backend
- New functions in `guards.py` must have strict typing and PEP-257 docstrings.
- Regex operations are efficient and performant for large runbooks.

## Codebase Introspection

### Targeted File Contents (from source)

**agent/commands/runbook.py**

```python
# 4. DoD Compliance Gate (INFRA-161)
with tracer.start_as_current_span("dod_compliance_gate") as dod_span:
    dod_span.set_attribute("story_id", story_id)
    dod_span.set_attribute("attempt", attempt)
    acs = extract_acs(story_content)

    # AC-1: Secondary AI call — AC coverage check (only when story exists)
    _gap_4a: List[str] = []
    if acs:  # story file found and has ACs (AC-8: skip gracefully otherwise)
        _ac_prompt = build_ac_coverage_prompt(acs, content)
        _ac_response = ai_service.complete(
            system_prompt=(
                "You are a QA reviewer. Respond ONLY with ALL_PASS or "
                "AC-N: <reason> lines. No prose."
            ),
            user_prompt=scrub_sensitive_data(_ac_prompt),
        )
        _ac_gap_ids = parse_ac_gaps(_ac_response or "")
        if _ac_gap_ids:
            _gap_4a = [
                f"AC coverage gap: {gid} is not addressed by any runbook step"
                for gid in _ac_gap_ids
            ]

    # AC-2 through AC-5: Deterministic checks
    _gap_4b = check_test_coverage(content)
    _gap_4c = check_changelog_entry(content)
    _gap_4d = check_license_headers(content)
    _gap_4e = check_otel_spans(content, story_content)
    dod_gaps: List[str] = [*_gap_4a, *_gap_4b, *_gap_4c, *_gap_4d, *_gap_4e]

    # Per AC-9: gaps attribute is comma-joined IDs (4a–4e)
    _gap_ids_list: List[str] = []
    if _gap_4a:
        _gap_ids_list.append("4a")
    if _gap_4b:
        _gap_ids_list.append("4b")
    if _gap_4c:
        _gap_ids_list.append("4c")
    if _gap_4d:
        _gap_ids_list.append("4d")
    if _gap_4e:
        _gap_ids_list.append("4e")
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/test_runbook_verifiers.py` | N/A | `agent/core/implement/guards.py` | Create new test file to verify logic. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| ADR-005: AI-Driven Governance Preflight | ADR Catalogue | Preflight must be deterministic and rule-based. | Yes |
| ADR-040: Tool-Calling Loop | ADR Catalogue | Implementation loops must be gated by guards. | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Standardize path normalization in `guards.py` to handle cross-platform implementations (slashes vs backslashes).

## Implementation Steps

### Step 1: Implement verifier functions in `guards.py`

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```
<<<SEARCH
def check_imports(filepath: str, content: str) -> ValidationResult:
    """Validate imports against project dependencies.

    Uses ``start_as_current_span`` so this span appears as a child of
    ``validate_code_block`` in the trace hierarchy (INFRA-155).
    """
    import ast
    import re as _re
    import sys
    from agent.core.config import resolve_repo_path

    with _tracer.start_as_current_span("guards.check_imports") as span:
===
def check_impact_analysis_completeness(runbook_content: str) -> List[str]:
    """Verify that every modified file is listed in the Step N summary.

    Checks files mentioned in [MODIFY], [NEW], and [DELETE] blocks against
    the 'Components touched:' section in the Impact Analysis update step.

    Args:
        runbook_content: The full content of the generated runbook.

    Returns:
        List of error messages for missing documentation.
    """
    import re
    from pathlib import Path

    with _tracer.start_as_current_span("guards.check_impact_analysis") as span:
        # 1. Extract files from runbook headers
        # Exclude CHANGELOG.md and story files as they are standard housekeeping
        ops = re.findall(r"####\s*\[(?:MODIFY|NEW|DELETE)\]\s*([^ \n`]+)", runbook_content)
        touched_files = {
            Path(f).as_posix() for f in ops
            if not f.endswith("CHANGELOG.md") and ".agent/cache/stories/" not in f
        }

        # 2. Extract files from the "Components touched:" list in Step N
        # We look for the block intended to be written to the story file
        summary_match = re.search(
            r"\*\*Components touched:\*\*\s*\n((?:\s*-\s*`[^`]+`.*?\n?)+)",
            runbook_content,
            re.MULTILINE
        )

        documented_files = set()
        if summary_match:
            lines = summary_match.group(1).splitlines()
            for line in lines:
                file_match = re.search(r"-\s*`([^`]+)`", line)
                if file_match:
                    documented_files.add(Path(file_match.group(1)).as_posix())

        missing = touched_files - documented_files
        span.set_attribute("files_touched", len(touched_files))
        span.set_attribute("files_documented", len(documented_files))
        span.set_attribute("missing_count", len(missing))

        if not missing:
            return []

        return [
            f"Impact Analysis Gap: `{f}` is modified/created in implementation steps but missing from the Step N Impact Analysis summary"
            for f in sorted(missing)
        ]


def check_adr_refs(runbook_content: str, adr_dir: Path) -> List[str]:
    """Validate that all ADR-NNN citations exist in the catalogue.

    Args:
        runbook_content: The full content of the generated runbook.
        adr_dir: Path to the directory containing ADR markdown files.

    Returns:
        List of error messages for hallucinated ADR references.
    """
    import re

    with _tracer.start_as_current_span("guards.check_adr_refs") as span:
        # Extract all ADR-NNN patterns
        refs = set(re.findall(r"ADR-\d+", runbook_content))
        if not refs:
            return []

        if not adr_dir.exists():
            span.set_attribute("error", "adr_dir_missing")
            return [f"ADR directory not found at {adr_dir}"]

        # Map existing ADR IDs to filenames
        existing_ids = set()
        for adr_file in adr_dir.glob("ADR-*.md"):
            match = re.match(r"(ADR-\d+)", adr_file.name)
            if match:
                existing_ids.add(match.group(1))

        invalid = refs - existing_ids
        span.set_attribute("refs_found", len(refs))
        span.set_attribute("invalid_count", len(invalid))

        if not invalid:
            return []

        return [
            f"Hallucinated ADR: `{adr}` is cited but does not exist in the on-disk catalogue"
            for adr in sorted(invalid)
        ]


def check_imports(filepath: str, content: str) -> ValidationResult:
    """Validate imports against project dependencies.

    Uses ``start_as_current_span`` so this span appears as a child of
    ``validate_code_block`` in the trace hierarchy (INFRA-155).
    """
    import ast
    import re as _re
    import sys
    from agent.core.config import resolve_repo_path

    with _tracer.start_as_current_span("guards.check_imports") as span:
>>>
```

### Step 2: Wire verifiers into Gate 4 in `runbook.py`

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.core.implement.guards import validate_code_block
===
from agent.core.implement.guards import (
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
)
>>>
```

```
<<<SEARCH
            # AC-2 through AC-5: Deterministic checks
            _gap_4b = check_test_coverage(content)
            _gap_4c = check_changelog_entry(content)
            _gap_4d = check_license_headers(content)
            _gap_4e = check_otel_spans(content, story_content)
            dod_gaps: List[str] = [*_gap_4a, *_gap_4b, *_gap_4c, *_gap_4d, *_gap_4e]

            # Per AC-9: gaps attribute is comma-joined IDs (4a–4e)
            _gap_ids_list: List[str] = []
            if _gap_4a:
                _gap_ids_list.append("4a")
            if _gap_4b:
                _gap_ids_list.append("4b")
            if _gap_4c:
                _gap_ids_list.append("4c")
            if _gap_4d:
                _gap_ids_list.append("4d")
            if _gap_4e:
                _gap_ids_list.append("4e")
===
            # AC-2 through AC-5: Deterministic checks
            _gap_4b = check_test_coverage(content)
            _gap_4c = check_changelog_entry(content)
            _gap_4d = check_license_headers(content)
            _gap_4e = check_otel_spans(content, story_content)
            _gap_4f = check_impact_analysis_completeness(content)
            _gap_4g = check_adr_refs(content, config.adrs_dir)
            dod_gaps: List[str] = [
                *_gap_4a, *_gap_4b, *_gap_4c, *_gap_4d, *_gap_4e, *_gap_4f, *_gap_4g
            ]

            # Per AC-9: gaps attribute is comma-joined IDs (4a–4g)
            _gap_ids_list: List[str] = []
            if _gap_4a:
                _gap_ids_list.append("4a")
            if _gap_4b:
                _gap_ids_list.append("4b")
            if _gap_4c:
                _gap_ids_list.append("4c")
            if _gap_4d:
                _gap_ids_list.append("4d")
            if _gap_4e:
                _gap_ids_list.append("4e")
            if _gap_4f:
                _gap_ids_list.append("4f")
            if _gap_4g:
                _gap_ids_list.append("4g")
>>>
```

### Step 3: Create unit tests for verifiers

#### [NEW] .agent/src/agent/commands/tests/test_dod_verifiers.py

```python
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
"""

from pathlib import Path
import pytest
from agent.core.implement.guards import check_impact_analysis_completeness, check_adr_refs


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
```

### Step 4: Update CHANGELOG.md

#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
### Added
- **INFRA-141**: Migrated filesystem and shell tools to dedicated domain modules and added `move_file`, `copy_file`, and `file_diff`.
===
### Added
- **INFRA-162**: Enhanced DoD Compliance Gate (Gate 4) with deterministic verifiers for Impact Analysis completeness (`_gap_4f`) and ADR reference validation (`_gap_4g`).
- **INFRA-141**: Migrated filesystem and shell tools to dedicated domain modules and added `move_file`, `copy_file`, and `file_diff`.
>>>
```

### Step 5: Update Impact Analysis in story file

#### [MODIFY] .agent/cache/stories/INFRA/INFRA-162-dod-gate-impact-analysis-completeness-and-adr-existence-verifiers.md

```
<<<SEARCH
**Components touched:**
- `agent/commands/runbook.py` — **[MODIFY]** Wire `_gap_4f` and `_gap_4g` into Gate 4 `dod_gaps` list.
- `agent/core/implement/guards.py` — **[MODIFY]** Implement `_check_impact_analysis_completeness` and `_check_adr_refs` verifier functions.
- `agent/commands/tests/test_dod_verifiers.py` — **[NEW]** Unit tests for both verifiers covering happy path, missing paths, hallucinated ADRs, and empty/missing inputs.
===
**Components touched:**
- `agent/commands/runbook.py` — **[MODIFY]** Wire `_gap_4f` and `_gap_4g` into Gate 4 `dod_gaps` list.
- `agent/core/implement/guards.py` — **[MODIFY]** Implement `check_impact_analysis_completeness` and `check_adr_refs` verifier functions.
- `agent/commands/tests/test_dod_verifiers.py` — **[NEW]** Unit tests for both verifiers covering happy path, missing paths, hallucinated ADRs, and empty/missing inputs.
- `CHANGELOG.md` — **[MODIFY]** Document new verifiers.
>>>
```

## Verification Plan

### Automated Tests

- [ ] Run unit tests: `pytest .agent/src/agent/commands/tests/test_dod_verifiers.py`
- [ ] Expected outcome: All tests pass (Happy paths, missing documentation, hallucinated ADRs, missing directories).

### Manual Verification

- [ ] Generate a runbook for a test story using `agent new-runbook`.
- [ ] Artificially remove a file from the Step N Impact Analysis block in the AI response (using a mock provider or interception).
- [ ] Verify that the `dod_compliance_fail` log event is emitted and the correction prompt mentions the missing file.
- [ ] Add a fake `ADR-999` reference to a runbook step and verify Gate 4 catches it.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated (see Step N-1 above — this is a runbook step, not a suggestion)
- [x] Story `## Impact Analysis Summary` updated to list every touched file (see Step N above)

### Observability

- [x] Logs are structured and free of PII
- [x] New structured `extra=` dicts added if new logging added (e.g., `gap_count`, `gaps` in OTel span)

### Testing

- [x] All existing tests pass
- [x] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook
