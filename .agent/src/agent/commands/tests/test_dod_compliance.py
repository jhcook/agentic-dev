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
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    parse_ac_gaps,
)

# ---------------------------------------------------------------------------
# Fixtures — use string concat to avoid nested triple-backtick fence issues
# ---------------------------------------------------------------------------

AC_STORY = (
    "## Acceptance Criteria\n\n"
    "- [ ] Gate 4 verifies CHANGELOG entry\n"
    "- [ ] Gate 4 verifies at least one test file step\n"
    "- [x] Already done item\n"
)

RUNBOOK_WITH_TEST = (
    "### Step 1\n"
    "#### [NEW] .agent/src/agent/commands/tests/test_foo.py\n"
)

RUNBOOK_NO_TEST = (
    "### Step 1\n"
    "#### [NEW] .agent/src/agent/commands/foo.py\n"
)

RUNBOOK_WITH_CHANGELOG = "### Step 2\n#### [MODIFY] CHANGELOG.md\n"
RUNBOOK_NO_CHANGELOG = "### Step 2\n#### [MODIFY] README.md\n"

_FENCE = "```"
RUNBOOK_NEW_PY_WITH_HEADER = (
    "#### [NEW] .agent/src/agent/commands/bar.py\n\n"
    + _FENCE + "python\n"
    "# Copyright 2024 Google LLC\n"
    "# Licensed under the Apache License, Version 2.0 (the \"License\")\n"
    "def foo():\n"
    "    pass\n"
    + _FENCE + "\n"
)

RUNBOOK_NEW_PY_NO_HEADER = (
    "#### [NEW] .agent/src/agent/commands/bar.py\n\n"
    + _FENCE + "python\n"
    "def foo():\n"
    "    pass\n"
    + _FENCE + "\n"
)

STORY_OTEL = "This story requires OpenTelemetry tracing for the new flow."
STORY_NO_OTEL = "This story adds a simple helper function."

RUNBOOK_WITH_SPAN = (
    "#### [MODIFY] .agent/src/agent/commands/runbook.py\n"
    + _FENCE + "\n"
    "tracer.start_as_current_span(\"my_span\")\n"
    + _FENCE + "\n"
)

RUNBOOK_TOUCHES_COMMANDS_NO_SPAN = (
    "#### [NEW] .agent/src/agent/commands/foo.py\n"
    + _FENCE + "python\n"
    "def bar():\n"
    "    pass\n"
    + _FENCE + "\n"
)


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

    def test_prose_mention_does_not_pass(self) -> None:
        """A prose mention of CHANGELOG should NOT satisfy the check.

        This is a regression test for the false-positive bug caught by the
        governance panel — 'CHANGELOG' in a comment or description was
        previously treated as a passing step.
        """
        prose = "### Overview\nThis runbook updates the CHANGELOG section.\n"
        gaps = check_changelog_entry(prose)
        assert len(gaps) == 1, "prose mention should not satisfy the check"


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
        runbook = (
            "#### [NEW] .agent/templates/foo.md\n\n"
            + _FENCE + "\nsome content\n" + _FENCE + "\n"
        )
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


# ---------------------------------------------------------------------------
# build_ac_coverage_prompt
# ---------------------------------------------------------------------------

class TestBuildAcCoveragePrompt:
    """Tests for build_ac_coverage_prompt()."""

    def test_contains_numbered_acs(self) -> None:
        """Should include numbered AC lines in the prompt."""
        acs = ["Implement the gate", "Add OTel spans"]
        prompt = build_ac_coverage_prompt(acs, "### Implementation Steps\nStep 1.\n")
        assert "AC-1: Implement the gate" in prompt
        assert "AC-2: Add OTel spans" in prompt

    def test_contains_all_pass_instruction(self) -> None:
        """Prompt should instruct AI to return ALL_PASS when all ACs covered."""
        acs = ["Implement the gate"]
        prompt = build_ac_coverage_prompt(acs, "")
        assert "ALL_PASS" in prompt

    def test_contains_format_instruction(self) -> None:
        """Prompt should specify the AC-N: <reason> response format."""
        acs = ["Implement the gate"]
        prompt = build_ac_coverage_prompt(acs, "")
        assert "AC-N:" in prompt or "AC-1:" in prompt

    def test_empty_acs_produces_prompt(self) -> None:
        """Should not raise when called with an empty ACs list."""
        prompt = build_ac_coverage_prompt([], "No steps.")
        assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# parse_ac_gaps
# ---------------------------------------------------------------------------

class TestParseAcGaps:
    """Tests for parse_ac_gaps()."""

    def test_all_pass_returns_empty(self) -> None:
        """ALL_PASS response should return an empty list."""
        assert parse_ac_gaps("ALL_PASS") == []

    def test_empty_response_returns_empty(self) -> None:
        """Empty / whitespace response should return an empty list."""
        assert parse_ac_gaps("") == []
        assert parse_ac_gaps("   ") == []

    def test_single_gap_parsed(self) -> None:
        """Single AC-N: line should be parsed correctly."""
        gaps = parse_ac_gaps("AC-3: No test step found in runbook")
        assert gaps == ["AC-3"]

    def test_multiple_gaps_parsed(self) -> None:
        """Multiple AC-N: lines should all be returned."""
        response = "AC-1: Missing OTel span\nAC-4: No CHANGELOG step"
        gaps = parse_ac_gaps(response)
        assert "AC-1" in gaps
        assert "AC-4" in gaps
        assert len(gaps) == 2

    def test_prose_with_all_pass_returns_empty(self) -> None:
        """ALL_PASS anywhere in the response should short-circuit to empty."""
        assert parse_ac_gaps("Looks good. ALL_PASS") == []
