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

"""Journey tests for JRN-064: Forecast-Gated Story Decomposition.

Tests the forecast gate (Layer 1) that intercepts over-budget stories
and produces decomposition plans instead of runbooks.
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from agent.commands.runbook import (
    score_story_complexity,
    ComplexityMetrics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WITHIN_BUDGET_STORY = """\
# Story: INFRA-TEST

## State
COMMITTED

## Acceptance Criteria
- [ ] Add a single utility function
- [ ] Write unit tests

#### [MODIFY] `src/utils.py`
#### [MODIFY] `tests/test_utils.py`
"""

OVER_BUDGET_STORY_LOC = """\
# Story: INFRA-BIG

## State
COMMITTED

## Acceptance Criteria
- [ ] Step 1: Migrate old auth system
- [ ] Step 2: Migrate user model
- [ ] Step 3: Migrate session handling
- [ ] Step 4: Migrate token validation
- [ ] Step 5: Migrate rate limiting
- [ ] Step 6: Migrate logging
- [ ] Step 7: Migrate error handling
- [ ] Step 8: Migrate health checks
- [ ] Step 9: Migrate integration tests
- [ ] Step 10: Migrate deployment config
- [ ] Step 11: Migrate documentation

#### [MODIFY] `src/auth.py`
#### [NEW] `src/auth_v2.py`
#### [MODIFY] `src/models.py`
"""

OVER_BUDGET_STORY_FILES = """\
# Story: INFRA-WIDE

## State
COMMITTED

## Acceptance Criteria
- [ ] Add feature A
- [ ] Add feature B

#### [MODIFY] `src/a.py`
#### [MODIFY] `src/b.py`
#### [NEW] `src/c.py`
#### [NEW] `src/d.py`
#### [MODIFY] `src/e.py`
"""

REFACTOR_STORY = """\
# Story: INFRA-REFACTOR

## State
COMMITTED

## Acceptance Criteria
- [ ] Refactor the parser module
- [ ] Refactor the validator module
- [ ] Refactor the serializer module
- [ ] Refactor the handler module

#### [MODIFY] `src/parser.py`
"""


# ---------------------------------------------------------------------------
# Step 1: Forecast Gate Executes Before Runbook Generation
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestForecastGateScoring:
    """Step 1: CLI invokes the Forecast Gate. A lightweight AI call estimates
    the story's complexity score."""

    def test_scoring_returns_complexity_metrics(self):
        """Complexity score is calculated with all expected fields."""
        metrics = score_story_complexity(WITHIN_BUDGET_STORY)
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.step_count == 2
        assert metrics.context_width >= 0
        assert metrics.verb_intensity == 1.0
        assert metrics.estimated_loc == 80.0  # 2 steps * 40
        assert metrics.file_count == 2

    def test_scoring_detects_migrate_verb(self):
        """Verb intensity increases for 'migrate' stories."""
        metrics = score_story_complexity(OVER_BUDGET_STORY_LOC)
        assert metrics.verb_intensity == 2.0

    def test_scoring_detects_refactor_verb(self):
        """Verb intensity increases for 'refactor' stories."""
        metrics = score_story_complexity(REFACTOR_STORY)
        assert metrics.verb_intensity == 1.5

    def test_scoring_counts_file_markers(self):
        """File count captures MODIFY, NEW, DELETE, ADD markers."""
        metrics = score_story_complexity(OVER_BUDGET_STORY_FILES)
        assert metrics.file_count == 5


# ---------------------------------------------------------------------------
# Step 2: Forecast Gate Determines Over-Budget
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestForecastGateDecision:
    """Step 2: Forecast Gate determines the story is over-budget."""

    def test_within_budget_passes_gate(self):
        """A small story passes all thresholds."""
        metrics = score_story_complexity(WITHIN_BUDGET_STORY)
        is_over = (
            metrics.estimated_loc > 400
            or metrics.step_count > 8
            or metrics.file_count > 4
        )
        assert not is_over

    def test_over_budget_loc_fails_gate(self):
        """11 migrate steps = 880 estimated LOC > 400 threshold."""
        metrics = score_story_complexity(OVER_BUDGET_STORY_LOC)
        assert metrics.estimated_loc > 400

    def test_over_budget_files_fails_gate(self):
        """5 file markers > 4 file threshold."""
        metrics = score_story_complexity(OVER_BUDGET_STORY_FILES)
        assert metrics.file_count > 4

    def test_boundary_exactly_at_threshold(self):
        """Threshold is inclusive: exactly 400 LOC passes."""
        # 10 steps * 40 LOC * 1.0 verb = 400 LOC — should PASS
        story = "## State\nCOMMITTED\n"
        for i in range(10):
            story += f"- [ ] Step {i+1}\n"
        story += "#### [MODIFY] `a.py`\n"
        metrics = score_story_complexity(story)
        assert metrics.estimated_loc == 400
        is_over = metrics.estimated_loc > 400
        assert not is_over  # Inclusive: 400 passes, 401 would fail


# ---------------------------------------------------------------------------
# Step 3: Developer Reviews Generated Plan (integration)
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestDecompositionPlanGeneration:
    """Step 2-3: When over-budget, a Plan file is created instead of a Runbook."""

    @patch("agent.commands.runbook.config")
    def test_generates_plan_for_over_budget_story(self, mock_config, tmp_path):
        """Decomposition plan is generated and written to disk."""
        from agent.commands.runbook import generate_decomposition_plan

        mock_config.plans_dir = tmp_path / "plans"

        plan_content = (
            "# Plan: INFRA-BIG\n\n"
            "## Child Stories\n"
            "1. INFRA-BIG-a: Auth migration\n"
            "2. INFRA-BIG-b: Model migration\n"
        )

        with patch("agent.core.ai.ai_service") as mock_ai:
            mock_ai.complete.return_value = plan_content
            plan_path = generate_decomposition_plan("INFRA-BIG", OVER_BUDGET_STORY_LOC)

        assert Path(plan_path).exists()
        content = Path(plan_path).read_text()
        assert "Child Stories" in content
        assert "INFRA-BIG-a" in content
        assert "INFRA-BIG-b" in content


# ---------------------------------------------------------------------------
# Step 4: Child Story Passes Forecast Gate
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestChildStoryPassesForecast:
    """Step 4: A child story from the Plan is within budget."""

    def test_child_story_within_budget(self):
        """A decomposed child story passes forecast gate."""
        child_story = """\
# Story: INFRA-BIG-a

## State
COMMITTED

## Acceptance Criteria
- [ ] Migrate auth module
- [ ] Write unit tests

#### [MODIFY] `src/auth.py`
#### [NEW] `tests/test_auth.py`
"""
        metrics = score_story_complexity(child_story)
        is_over = (
            metrics.estimated_loc > 400
            or metrics.step_count > 8
            or metrics.file_count > 4
        )
        assert not is_over


# ---------------------------------------------------------------------------
# Error Path: Story not COMMITTED
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestErrorPaths:
    """Error paths: invalid story state, missing story."""

    def test_non_committed_story_detected(self):
        """Stories not in COMMITTED state should be rejected by the CLI."""
        import re
        draft_story = "# Story\n\n## State\nDRAFT\n"
        state_pattern = r"(?:^State:\s*COMMITTED|^## State\s*\n+COMMITTED|^Status:\s*COMMITTED)"
        assert not re.search(state_pattern, draft_story, re.MULTILINE)


# ---------------------------------------------------------------------------
# Edge Case: --skip-forecast bypass
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestSkipForecastBypass:
    """Edge case: --skip-forecast bypasses the gate with audit logging."""

    def test_over_budget_metrics_detected_but_bypass_available(self):
        """Even when over-budget, --skip-forecast allows proceeding."""
        metrics = score_story_complexity(OVER_BUDGET_STORY_LOC)
        # Gate would fail...
        assert metrics.estimated_loc > 400
        # ...but skip_forecast=True bypasses it (tested at integration level
        # in the new_runbook command, here we verify the metrics are correct)


# ---------------------------------------------------------------------------
# Edge Case: SPLIT_REQUEST Fallback (Layer 2)
# ---------------------------------------------------------------------------

@pytest.mark.journey("JRN-064")
class TestSplitRequestFallback:
    """Error path: Forecast passes but AI detects over-limit during generation."""

    def test_parse_split_request_valid_json(self):
        """Valid SPLIT_REQUEST JSON is parsed correctly."""
        from agent.commands.runbook import _parse_split_request

        content = '{"SPLIT_REQUEST": true, "reason": "Too complex", "suggestions": ["Split A", "Split B"]}'
        result = _parse_split_request(content)
        assert result is not None
        assert result["SPLIT_REQUEST"] is True
        assert len(result["suggestions"]) == 2

    def test_parse_split_request_in_code_fence(self):
        """SPLIT_REQUEST in markdown code fence is extracted."""
        from agent.commands.runbook import _parse_split_request

        content = '```json\n{"SPLIT_REQUEST": true, "reason": "Big", "suggestions": ["A"]}\n```'
        result = _parse_split_request(content)
        assert result is not None
        assert result["SPLIT_REQUEST"] is True

    def test_parse_split_request_malformed_returns_none(self):
        """Malformed JSON with SPLIT_REQUEST marker falls back gracefully."""
        from agent.commands.runbook import _parse_split_request

        content = "SPLIT_REQUEST but not valid json at all"
        result = _parse_split_request(content)
        assert result is None
