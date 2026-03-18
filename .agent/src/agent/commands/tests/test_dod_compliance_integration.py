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
# Fixtures — use string concat to avoid nested triple-backtick fence issues
# ---------------------------------------------------------------------------

_FENCE = "```"

FULL_COMPLIANT_RUNBOOK = (
    "# INFRA-XXX: Test Runbook\n\n"
    "### Step 1: Add tests\n"
    "#### [NEW] .agent/src/agent/commands/tests/test_feature.py\n\n"
    + _FENCE + "python\n"
    "# Copyright 2024 Google LLC\n"
    "# Licensed under the Apache License, Version 2.0 (the \"License\")\n"
    "import pytest\n\n"
    "def test_feature():\n"
    "    assert True\n"
    + _FENCE + "\n\n"
    "### Step 2: Document change\n"
    "#### [MODIFY] CHANGELOG.md\n\n"
    "### Step 3: Add span\n"
    "#### [MODIFY] .agent/src/agent/commands/runbook.py\n\n"
    + _FENCE + "\n"
    "tracer.start_as_current_span(\"my_gate\")\n"
    + _FENCE + "\n"
)

FULL_NON_COMPLIANT_RUNBOOK = (
    "# INFRA-XXX: Test Runbook\n\n"
    "### Step 1: Add feature only\n"
    "#### [MODIFY] .agent/src/agent/commands/runbook.py\n\n"
    + _FENCE + "\n"
    "x = 1\n"
    + _FENCE + "\n"
)

STORY_WITH_OTEL = (
    "## Acceptance Criteria\n\n"
    "- [ ] Implement the gate\n"
    "- [ ] Add OTel tracing span\n\n"
    "This story requires OpenTelemetry span instrumentation.\n"
)


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
            assert gap[:30] in prompt

    def test_correction_prompt_contains_acs(self) -> None:
        """Correction prompt should include story ACs for AI context."""
        acs = extract_acs(STORY_WITH_OTEL)
        prompt = build_dod_correction_prompt(["gap"], STORY_WITH_OTEL, acs)
        assert "Implement the gate" in prompt
