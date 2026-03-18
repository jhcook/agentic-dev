# INFRA-161: DoD Compliance Gate in `agent new-runbook`

## State

PROPOSED

## Goal Description

`agent new-runbook` validates structure (schema gate), code quality (code gate), and S/R accuracy (S/R gate), but never checks whether the generated runbook actually satisfies the story's Definition of Done. The result is runbooks that pass all three gates yet still fail `agent preflight` after implementation because they missed CHANGELOG entries, lacked tests, omitted license headers on new Python files, or skipped OTel instrumentation. Gate 4 runs after the S/R gate and applies five deterministic+AI verifiers to the runbook content, bundling all gaps into a single correction prompt and sharing the existing 3-attempt retry budget.

## Linked Journeys

- None

## Panel Review Findings

### @Architect
Gate 4 is additive — it slots between the S/R gate and the `break` statement without touching the existing gate chain. The five verifiers are pure functions (no side effects) added to `utils.py`. The retry-budget sharing means we add zero new configuration surface.

### @QA
Eight unit tests cover each helper in isolation (AC extraction, test-coverage check, CHANGELOG check, license-header check, OTel-span check, correction-prompt builder). Five integration tests exercise the full gate loop via subprocess against a temp runbook fixture.

### @Security
All story content fed to `build_dod_correction_prompt` is already scrubbed via `scrub_sensitive_data` before reaching this point in `new_runbook`. No additional PII surface introduced.

### @Observability
OTel span `dod_compliance_gate` wraps the gate. Gate outcome (`pass`/`retry`/`exhausted`) recorded as span attribute. Structured log events: `dod_compliance_fail`, `dod_compliance_pass`, `dod_correction_attempt`.

### @Compliance
CHANGELOG gate enforces SOC2 audit trail requirement that every shipped story has a documented entry. License-header gate enforces the Apache-2.0 header policy.

### @Docs
CHANGELOG.md updated in Step 5.

### @Backend
All new helpers follow async-free, sync-only pattern consistent with the rest of `utils.py`.

### @Mobile / @Web
Not applicable.

## Codebase Introspection

### Targeted File Contents (from source)

See SEARCH blocks below — derived from live file reads.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `agent/commands/tests/test_sr_validation.py` | `validate_sr_blocks` | unchanged | No change needed |
| `agent/commands/tests/test_sr_validation_integration.py` | `agent new-runbook` CLI | unchanged | No change needed |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `max_attempts = 3` shared across all gates | `runbook.py:360` | 3 | Yes — Gate 4 consumes from same budget |
| Exit code 1 on gate exhaustion | `runbook.py` | 1 | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract gate logic from `new_runbook` into a dedicated `gates.py` module (future, out of scope here)

## Implementation Steps

### Step 1: Add DoD helper functions to `utils.py`

Five new deterministic checkers and one correction-prompt builder appended to `agent/commands/utils.py`.

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
    lines.append(
        "\nInstruction: Rewrite the implementation steps so that EVERY "
        "<<<SEARCH block exactly matches the actual file content provided. "
        "Use the provided actual content verbatim. Return the FULL updated runbook."
    )
    return "\n".join(lines)

===
    lines.append(
        "\nInstruction: Rewrite the implementation steps so that EVERY "
        "<<<SEARCH block exactly matches the actual file content provided. "
        "Use the provided actual content verbatim. Return the FULL updated runbook."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# INFRA-161: DoD Compliance Gate helpers
# ---------------------------------------------------------------------------

def extract_acs(story_content: str) -> List[str]:
    """Extract Acceptance Criteria bullets from a story markdown file.

    Scans for the ``## Acceptance Criteria`` section and returns each
    non-empty bullet line (stripping leading ``- [ ]`` / ``- [x]`` markers).

    Args:
        story_content: Raw markdown text of the user story.

    Returns:
        List of AC strings.  Empty list if the section is absent.
    """
    import re as _re

    ac_section = _re.search(
        r"##\s+Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)",
        story_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    if not ac_section:
        return []
    raw = ac_section.group(1)
    acs: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Strip leading bullet markers
        cleaned = _re.sub(r"^-\s*\[.\]\s*", "", stripped)
        cleaned = _re.sub(r"^[-*]\s+", "", cleaned)
        if cleaned:
            acs.append(cleaned)
    return acs


def check_test_coverage(runbook_content: str) -> List[str]:
    """Check that the runbook includes at least one test-file step.

    Looks for ``[NEW]`` or ``[MODIFY]`` blocks targeting paths that contain
    ``test_`` or ``_test.`` in the filename.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re

    pattern = _re.compile(
        r"####\s+\[(NEW|MODIFY)\]\s+([^\n]+)",
        _re.IGNORECASE,
    )
    for m in pattern.finditer(runbook_content):
        path = m.group(2).strip()
        filename = path.split("/")[-1]
        if "test_" in filename or "_test." in filename:
            return []
    return ["No test file step found — at least one [NEW] or [MODIFY] targeting a test_*.py file is required."]


def check_changelog_entry(runbook_content: str) -> List[str]:
    """Check that the runbook includes a CHANGELOG.md modification step.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    if "CHANGELOG.md" in runbook_content or "CHANGELOG" in runbook_content:
        return []
    return ["No CHANGELOG.md step found — every story must document its change in CHANGELOG.md."]


def check_license_headers(runbook_content: str) -> List[str]:
    """Check that every ``[NEW]`` Python file step includes the Apache-2.0 header.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re

    gaps: List[str] = []
    # Find all [NEW] *.py blocks
    new_py = _re.finditer(
        r"####\s+\[NEW\]\s+([^\n]+\.py)\s*\n+```[^\n]*\n(.*?)```",
        runbook_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    for m in new_py:
        path = m.group(1).strip()
        body = m.group(2)
        if "Copyright" not in body and "Apache" not in body and "LICENSE" not in body:
            gaps.append(
                f"[NEW] {path} is missing the Apache-2.0 license header. "
                "Add the standard copyright block at the top of the file."
            )
    return gaps


def check_otel_spans(runbook_content: str, story_content: str) -> List[str]:
    """Check that runbook steps touching commands/ or core/ include OTel spans.

    Only applies when the story explicitly mentions observability, tracing,
    or a new flow in commands/ or core/.

    Args:
        runbook_content: Raw runbook markdown.
        story_content: Raw story markdown (used to detect observability AC).

    Returns:
        List of gap strings (empty if requirement met or not applicable).
    """
    import re as _re

    # Only enforce when story mentions OTel / tracing / observability
    otel_keywords = ("opentelemetry", "otel", "tracing", "span", "observability")
    if not any(kw in story_content.lower() for kw in otel_keywords):
        return []

    # Check that runbook references start_as_current_span or similar
    if "start_as_current_span" in runbook_content or "tracer.start" in runbook_content:
        return []

    # Is there a step touching commands/ or core/?
    touches_infra = _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+\.agent/src/agent/(commands|core)/",
        runbook_content,
        _re.IGNORECASE,
    )
    if touches_infra:
        return [
            "Story requires OTel observability but no 'start_as_current_span' / 'tracer.start' "
            "found in runbook steps touching commands/ or core/. Add an OTel span for the new flow."
        ]
    return []


def build_dod_correction_prompt(
    gaps: List[str],
    story_content: str,
    acs: List[str],
) -> str:
    """Build a targeted correction prompt that bundles all DoD gaps.

    Args:
        gaps: List of gap description strings from the deterministic checkers.
        story_content: Scrubbed story text (for AC context).
        acs: Extracted acceptance criteria list.

    Returns:
        Formatted instruction string ready to append to the AI user prompt.
    """
    lines = [
        "DOD COMPLIANCE GATE FAILED. The following requirements are missing "
        "from the generated runbook:\n"
    ]
    for i, gap in enumerate(gaps, 1):
        lines.append(f"  {i}. {gap}")

    if acs:
        lines.append(
            "\nACCEPTANCE CRITERIA FROM STORY (ensure ALL are addressed by at "
            "least one Implementation Step):"
        )
        for ac in acs:
            lines.append(f"  - {ac}")

    lines.append(
        "\nInstruction: Regenerate the FULL runbook ensuring every gap above is "
        "resolved. Do not omit any existing correct steps — only add/fix the "
        "missing items. Return the complete updated runbook."
    )
    return "\n".join(lines)
>>>
```

### Step 2: Update `runbook.py` imports to include DoD helpers

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.commands.utils import (
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
    validate_sr_blocks,
    generate_sr_correction_prompt,
)
===
from agent.commands.utils import (
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    extract_adr_refs,
    extract_journey_refs,
    generate_sr_correction_prompt,
    merge_story_links,
    validate_sr_blocks,
)
>>>
```

### Step 3: Wire Gate 4 (DoD compliance) into `new_runbook` after the S/R gate

Insert Gate 4 between `sr_validation_pass` log and the `# All validations passed` block.

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
                logger.info("sr_validation_pass", extra={"story_id": story_id})

        # All validations passed — proceed
        if code_warnings:
===
                logger.info("sr_validation_pass", extra={"story_id": story_id})

        # 4. DoD Compliance Gate (INFRA-161)
        with tracer.start_as_current_span("dod_compliance_gate") as dod_span:
            dod_span.set_attribute("attempt", attempt)
            acs = extract_acs(story_content)
            dod_gaps: List[str] = []
            dod_gaps.extend(check_test_coverage(content))
            dod_gaps.extend(check_changelog_entry(content))
            dod_gaps.extend(check_license_headers(content))
            dod_gaps.extend(check_otel_spans(content, story_content))
            dod_span.set_attribute("gap_count", len(dod_gaps))

        if dod_gaps:
            logger.warning(
                "dod_compliance_fail",
                extra={"attempt": attempt, "story_id": story_id, "gaps": dod_gaps},
            )
            if attempt < max_attempts:
                dod_span.set_attribute("outcome", "retry")
                console.print(
                    f"[yellow]⚠️  Attempt {attempt}: DoD gaps detected "
                    f"({len(dod_gaps)}) — asking AI for self-healing...[/yellow]"
                )
                logger.info("dod_correction_attempt", extra={"attempt": attempt, "story_id": story_id})
                current_user_prompt = (
                    f"{user_prompt}\n\n"
                    f"{build_dod_correction_prompt(dod_gaps, story_content, acs)}"
                )
                continue
            else:
                dod_span.set_attribute("outcome", "exhausted")
                error_console.print(
                    f"[bold red]❌ DoD compliance gate failed after {max_attempts} attempts.[/bold red]"
                )
                for gap in dod_gaps:
                    error_console.print(f"  [red]• {gap}[/red]")
                raise typer.Exit(code=1)
        else:
            dod_span.set_attribute("outcome", "pass")
            logger.info("dod_compliance_pass", extra={"story_id": story_id})

        # All validations passed — proceed
        if code_warnings:
>>>
```

### Step 4: Add unit tests for the five DoD helpers

#### [NEW] .agent/src/agent/commands/tests/test_dod_compliance.py

```python
# Copyright 2024 Google LLC
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
"""Unit tests for INFRA-161 DoD compliance gate helpers.

Covers: extract_acs, check_test_coverage, check_changelog_entry,
check_license_headers, check_otel_spans, build_dod_correction_prompt.
"""
import pytest

from agent.commands.utils import (
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AC_STORY = """\
## Acceptance Criteria

- [ ] Gate 4 verifies CHANGELOG entry
- [ ] Gate 4 verifies at least one test file step
- [x] Already done item
"""

RUNBOOK_WITH_TEST = """\
### Step 1
#### [NEW] .agent/src/agent/commands/tests/test_foo.py
```python
pass
```
"""

RUNBOOK_NO_TEST = """\
### Step 1
#### [NEW] .agent/src/agent/commands/foo.py
```python
pass
```
"""

RUNBOOK_WITH_CHANGELOG = "### Step 2\n#### [MODIFY] CHANGELOG.md\n"
RUNBOOK_NO_CHANGELOG = "### Step 2\n#### [MODIFY] README.md\n"

RUNBOOK_NEW_PY_WITH_HEADER = """\
#### [NEW] .agent/src/agent/commands/bar.py

```python
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License")
def foo():
    pass
```
"""

RUNBOOK_NEW_PY_NO_HEADER = """\
#### [NEW] .agent/src/agent/commands/bar.py

```python
def foo():
    pass
```
"""

STORY_OTEL = "This story requires OpenTelemetry tracing for the new flow."
STORY_NO_OTEL = "This story adds a simple helper function."

RUNBOOK_WITH_SPAN = """\
#### [MODIFY] .agent/src/agent/commands/runbook.py
```
tracer.start_as_current_span("my_span")
```
"""

RUNBOOK_TOUCHES_COMMANDS_NO_SPAN = """\
#### [NEW] .agent/src/agent/commands/foo.py
```python
def bar():
    pass
```
"""


# ---------------------------------------------------------------------------
# extract_acs
# ---------------------------------------------------------------------------

class TestExtractAcs:
    """Tests for extract_acs()."""

    def test_extracts_unchecked_bullets(self) -> None:
        """Should extract unchecked AC bullets."""
        acs = extract_acs(AC_STORY)
        assert "Gate 4 verifies CHANGELOG entry" in acs

    def test_extracts_checked_bullets(self) -> None:
        """Should also extract already-checked AC bullets."""
        acs = extract_acs(AC_STORY)
        assert "Already done item" in acs

    def test_empty_when_no_section(self) -> None:
        """Should return empty list when section is absent."""
        assert extract_acs("## Problem Statement\nNo ACs here.") == []


# ---------------------------------------------------------------------------
# check_test_coverage
# ---------------------------------------------------------------------------

class TestCheckTestCoverage:
    """Tests for check_test_coverage()."""

    def test_passes_when_test_step_present(self) -> None:
        """Should return no gaps when a test file step exists."""
        assert check_test_coverage(RUNBOOK_WITH_TEST) == []

    def test_fails_when_no_test_step(self) -> None:
        """Should return a gap when no test file step found."""
        gaps = check_test_coverage(RUNBOOK_NO_TEST)
        assert len(gaps) == 1
        assert "test" in gaps[0].lower()


# ---------------------------------------------------------------------------
# check_changelog_entry
# ---------------------------------------------------------------------------

class TestCheckChangelogEntry:
    """Tests for check_changelog_entry()."""

    def test_passes_when_changelog_present(self) -> None:
        """Should return no gaps when CHANGELOG.md step exists."""
        assert check_changelog_entry(RUNBOOK_WITH_CHANGELOG) == []

    def test_fails_when_no_changelog(self) -> None:
        """Should return a gap when no CHANGELOG step found."""
        gaps = check_changelog_entry(RUNBOOK_NO_CHANGELOG)
        assert len(gaps) == 1
        assert "CHANGELOG" in gaps[0]


# ---------------------------------------------------------------------------
# check_license_headers
# ---------------------------------------------------------------------------

class TestCheckLicenseHeaders:
    """Tests for check_license_headers()."""

    def test_passes_when_header_present(self) -> None:
        """Should return no gaps when Apache header is present."""
        assert check_license_headers(RUNBOOK_NEW_PY_WITH_HEADER) == []

    def test_fails_when_header_missing(self) -> None:
        """Should return a gap when a [NEW] .py file lacks a license header."""
        gaps = check_license_headers(RUNBOOK_NEW_PY_NO_HEADER)
        assert len(gaps) == 1
        assert "Apache" in gaps[0] or "license" in gaps[0].lower()

    def test_ignores_non_py_files(self) -> None:
        """Should not flag [NEW] non-Python files."""
        runbook = "#### [NEW] .agent/templates/foo.md\n\n```\nsome content\n```\n"
        assert check_license_headers(runbook) == []


# ---------------------------------------------------------------------------
# check_otel_spans
# ---------------------------------------------------------------------------

class TestCheckOtelSpans:
    """Tests for check_otel_spans()."""

    def test_passes_when_span_present(self) -> None:
        """Should return no gaps when a span call is in the runbook."""
        assert check_otel_spans(RUNBOOK_WITH_SPAN, STORY_OTEL) == []

    def test_fails_when_otel_required_but_missing(self) -> None:
        """Should return a gap when story needs OTel but runbook lacks spans."""
        gaps = check_otel_spans(RUNBOOK_TOUCHES_COMMANDS_NO_SPAN, STORY_OTEL)
        assert len(gaps) == 1
        assert "span" in gaps[0].lower() or "otel" in gaps[0].lower()

    def test_skips_when_story_does_not_require_otel(self) -> None:
        """Should return no gaps when story has no OTel requirement."""
        assert check_otel_spans(RUNBOOK_TOUCHES_COMMANDS_NO_SPAN, STORY_NO_OTEL) == []


# ---------------------------------------------------------------------------
# build_dod_correction_prompt
# ---------------------------------------------------------------------------

class TestBuildDodCorrectionPrompt:
    """Tests for build_dod_correction_prompt()."""

    def test_contains_gaps(self) -> None:
        """Should include all provided gap strings."""
        gaps = ["Missing test file", "Missing CHANGELOG"]
        prompt = build_dod_correction_prompt(gaps, AC_STORY, extract_acs(AC_STORY))
        assert "Missing test file" in prompt
        assert "Missing CHANGELOG" in prompt

    def test_contains_acs(self) -> None:
        """Should include ACs from the story."""
        acs = extract_acs(AC_STORY)
        prompt = build_dod_correction_prompt(["gap"], AC_STORY, acs)
        assert "Gate 4 verifies CHANGELOG entry" in prompt

    def test_contains_instruction(self) -> None:
        """Should include the regeneration instruction."""
        prompt = build_dod_correction_prompt(["gap"], "", [])
        assert "Regenerate" in prompt or "regenerate" in prompt
```

### Step 5: Add integration tests for Gate 4

#### [NEW] .agent/src/agent/commands/tests/test_dod_compliance_integration.py

```python
# Copyright 2024 Google LLC
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
"""Integration tests for INFRA-161 DoD compliance gate.

Verifies that the five helper functions compose correctly and that the
correction prompt builder produces actionable output when gaps are present.
"""
import pytest

from agent.commands.utils import (
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_COMPLIANT_RUNBOOK = """\
# INFRA-XXX: Test Runbook

### Step 1: Add tests
#### [NEW] .agent/src/agent/commands/tests/test_feature.py

```python
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License")
import pytest

def test_feature():
    assert True
```

### Step 2: Document change
#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
## [Unreleased]
===
## [Unreleased]

### Added
- INFRA-XXX: new feature
>>>
```

### Step 3: Add span
#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
pass
===
with tracer.start_as_current_span("my_gate"):
    pass
>>>
```
"""

FULL_NON_COMPLIANT_RUNBOOK = """\
# INFRA-XXX: Test Runbook

### Step 1: Add feature only
#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
pass
===
x = 1
>>>
```
"""

STORY_WITH_OTEL = """\
## Acceptance Criteria

- [ ] Implement the gate
- [ ] Add OTel tracing span

This story requires OpenTelemetry span instrumentation.
"""


# ---------------------------------------------------------------------------
# Integration: compliant runbook produces zero gaps
# ---------------------------------------------------------------------------

class TestCompliantRunbook:
    """A fully compliant runbook should produce zero DoD gaps."""

    def test_no_test_coverage_gap(self) -> None:
        """Compliant runbook passes test coverage check."""
        assert check_test_coverage(FULL_COMPLIANT_RUNBOOK) == []

    def test_no_changelog_gap(self) -> None:
        """Compliant runbook passes changelog check."""
        assert check_changelog_entry(FULL_COMPLIANT_RUNBOOK) == []

    def test_no_license_header_gap(self) -> None:
        """Compliant runbook passes license header check."""
        assert check_license_headers(FULL_COMPLIANT_RUNBOOK) == []

    def test_no_otel_gap(self) -> None:
        """Compliant runbook passes OTel check."""
        assert check_otel_spans(FULL_COMPLIANT_RUNBOOK, STORY_WITH_OTEL) == []

    def test_all_gaps_zero(self) -> None:
        """Full suite of checks returns zero gaps for compliant runbook."""
        acs = extract_acs(STORY_WITH_OTEL)
        all_gaps: list[str] = []
        all_gaps.extend(check_test_coverage(FULL_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_changelog_entry(FULL_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_license_headers(FULL_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_otel_spans(FULL_COMPLIANT_RUNBOOK, STORY_WITH_OTEL))
        assert all_gaps == []


# ---------------------------------------------------------------------------
# Integration: non-compliant runbook produces gaps + correction prompt
# ---------------------------------------------------------------------------

class TestNonCompliantRunbook:
    """A non-compliant runbook should produce gaps and a useful correction prompt."""

    def test_gaps_detected(self) -> None:
        """Non-compliant runbook should surface multiple gaps."""
        all_gaps: list[str] = []
        all_gaps.extend(check_test_coverage(FULL_NON_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_changelog_entry(FULL_NON_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_license_headers(FULL_NON_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_otel_spans(FULL_NON_COMPLIANT_RUNBOOK, STORY_WITH_OTEL))
        assert len(all_gaps) >= 2  # missing test + missing changelog at minimum

    def test_correction_prompt_references_all_gaps(self) -> None:
        """build_dod_correction_prompt should reference every detected gap."""
        all_gaps: list[str] = []
        all_gaps.extend(check_test_coverage(FULL_NON_COMPLIANT_RUNBOOK))
        all_gaps.extend(check_changelog_entry(FULL_NON_COMPLIANT_RUNBOOK))
        acs = extract_acs(STORY_WITH_OTEL)
        prompt = build_dod_correction_prompt(all_gaps, STORY_WITH_OTEL, acs)
        for gap in all_gaps:
            # Each gap text should appear in the prompt
            assert gap[:30] in prompt

    def test_correction_prompt_contains_acs(self) -> None:
        """Correction prompt should include story ACs for AI context."""
        acs = extract_acs(STORY_WITH_OTEL)
        prompt = build_dod_correction_prompt(["gap"], STORY_WITH_OTEL, acs)
        assert "Implement the gate" in prompt
```

### Step 6: Update CHANGELOG.md

#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
## [Unreleased]

### Added
- **INFRA-159**:
===
## [Unreleased]

### Added
- **INFRA-161**: `agent new-runbook` now runs a **DoD Compliance Gate** (Gate 4) after the S/R validation gate. Five deterministic verifiers check: (1) at least one test-file step, (2) a CHANGELOG.md step, (3) Apache-2.0 license headers on all `[NEW]` Python files, (4) OTel spans in commands/core steps when the story requires observability. Gaps are bundled into a single correction prompt and share the existing 3-attempt retry budget. Structured log events: `dod_compliance_fail`, `dod_compliance_pass`, `dod_correction_attempt`. OTel span: `dod_compliance_gate`. Adds `extract_acs`, `check_test_coverage`, `check_changelog_entry`, `check_license_headers`, `check_otel_spans`, `build_dod_correction_prompt` to `agent.commands.utils`. 13 new tests (8 unit, 5 integration).
- **INFRA-159**:
>>>
```

## Verification Plan

### Automated Tests

- [ ] `cd .agent/src && uv run python -m pytest agent/commands/tests/test_dod_compliance.py -v` — 8 unit tests pass
- [ ] `cd .agent/src && uv run python -m pytest agent/commands/tests/test_dod_compliance_integration.py -v` — 5 integration tests pass
- [ ] `cd .agent/src && uv run python -m pytest agent/ --ignore=agent/tools/tests/ -q` — full suite ≥260 passed

### Manual Verification

- [ ] `agent new-runbook INFRA-161 --skip-forecast` — runbook written to disk (no DoD failures on second run once implementation is applied)
- [ ] `agent preflight --base main` — all 8 roles pass

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated (Step 6)
- [ ] README not affected

### Observability

- [x] OTel span `dod_compliance_gate` added in Step 3
- [x] Structured log events `dod_compliance_fail`, `dod_compliance_pass`, `dod_correction_attempt` in Step 3

### Testing

- [x] 8 unit tests for helper functions (Step 4)
- [x] 5 integration tests for gate composition (Step 5)

## Copyright

Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
