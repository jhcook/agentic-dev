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

"""Micro-commit circuit breaker for the implement command (INFRA-095).

Tracks cumulative lines-of-code edited across runbook steps and enforces
thresholds: a warning at LOC_WARNING_THRESHOLD and a hard halt with
follow-up story generation at LOC_CIRCUIT_BREAKER_THRESHOLD.
"""

import difflib
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

from agent.core.config import config
from agent.core.utils import get_next_id, scrub_sensitive_data

# ---------------------------------------------------------------------------
# Thresholds (INFRA-095)
# ---------------------------------------------------------------------------

MAX_EDIT_DISTANCE_PER_STEP: int = 30
LOC_WARNING_THRESHOLD: int = 200
LOC_CIRCUIT_BREAKER_THRESHOLD: int = 400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_branch_name(title: str) -> str:
    """Sanitize a story title for use in a git branch name."""
    name = title.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')


def count_edit_distance(original: str, modified: str) -> int:
    """Count line-level edit distance between two file contents.

    Uses unified-diff additions + deletions. Both empty strings returns 0.

    Args:
        original: Original file content (empty string for new files).
        modified: Modified file content.

    Returns:
        Number of lines changed (additions + deletions).
    """
    if not original and not modified:
        return 0
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, mod_lines, lineterm="")
    total = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            total += 1
        elif line.startswith("-") and not line.startswith("---"):
            total += 1
    return total


def micro_commit_step(
    story_id: str,
    step_index: int,
    step_loc: int,
    cumulative_loc: int,
    modified_files: List[str],
) -> bool:
    """Create a micro-commit save point for a single implementation step.

    Stages modified files and creates an atomic commit. Non-fatal on failure.

    Args:
        story_id: Story ID for the commit message.
        step_index: 1-based step index.
        step_loc: Lines changed in this step.
        cumulative_loc: Total lines changed so far.
        modified_files: Repo-relative file paths modified in this step.

    Returns:
        True if commit succeeded, False otherwise.
    """
    if not modified_files:
        return True
    try:
        subprocess.run(
            ["git", "add"] + modified_files,
            check=True, capture_output=True, timeout=30,
        )
        commit_msg = (
            f"feat({story_id}): implement step {step_index} "
            f"[{step_loc} LOC, {cumulative_loc} cumulative]"
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True, timeout=30,
        )
        logging.info(
            "save_point story=%s step=%d step_loc=%d cumulative_loc=%d",
            story_id, step_index, step_loc, cumulative_loc,
        )
        return True
    except subprocess.CalledProcessError as exc:
        logging.warning(
            "save_point_failed story=%s step=%d error=%s",
            story_id, step_index, exc,
        )
        return False


def create_follow_up_story(
    original_story_id: str,
    original_title: str,
    remaining_chunks: List[str],
    completed_step_count: int,
    cumulative_loc: int,
) -> Optional[str]:
    """Auto-generate a follow-up story when the circuit breaker activates.

    Creates a COMMITTED story referencing the remaining runbook steps.

    Args:
        original_story_id: Story ID that triggered the circuit breaker.
        original_title: Human-readable title of the original story.
        remaining_chunks: Unprocessed runbook chunk strings.
        completed_step_count: Number of steps already completed.
        cumulative_loc: LOC count at circuit breaker activation.

    Returns:
        New story ID if created successfully, None on failure.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    scope_dir = config.stories_dir / prefix
    scope_dir.mkdir(parents=True, exist_ok=True)
    new_story_id = get_next_id(scope_dir, prefix)

    remaining_summary = "\n".join(
        f"- Step {completed_step_count + i + 1}: {chunk[:200].strip()}"
        for i, chunk in enumerate(remaining_chunks)
    )
    content = f"""# {new_story_id}: {original_title} (Continuation)

## State

COMMITTED

## Problem Statement

Circuit breaker activated during implementation of {original_story_id} at {cumulative_loc} LOC cumulative.
This follow-up story contains the remaining implementation steps.

## User Story

As a **developer**, I want **the remaining steps from {original_story_id} implemented** so that **the full feature is completed across atomic PRs**.

## Acceptance Criteria

- [ ] Complete remaining implementation steps from {original_story_id} runbook.

## Remaining Steps from {original_story_id}

{remaining_summary}

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Related Stories

- {original_story_id} (parent — circuit breaker continuation)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation

## Impact Analysis Summary

Components touched: See remaining steps above.
Workflows affected: /implement
Risks: None beyond standard implementation risks.

## Test Strategy

- Follow the test strategy from the original {original_story_id} runbook.

## Rollback Plan

Revert changes from this follow-up story. The partial work from {original_story_id} remains intact.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
    safe_title = sanitize_branch_name(f"{original_title}-continuation")
    filename = f"{new_story_id}-{safe_title}.md"
    file_path = scope_dir / filename
    if file_path.exists():
        logging.error(
            "follow_up_story_collision path=%s story=%s", file_path, new_story_id
        )
        return None
    try:
        file_path.write_text(scrub_sensitive_data(content))
        logging.info(
            "follow_up_story_created story=%s parent=%s remaining_steps=%d",
            new_story_id, original_story_id, len(remaining_chunks),
        )
        return new_story_id
    except Exception as exc:
        logging.error("Failed to create follow-up story: %s", exc)
        return None


def update_or_create_plan(
    original_story_id: str,
    follow_up_story_id: str,
    original_title: str,
) -> None:
    """Link original and follow-up stories in a Plan document.

    Appends the follow-up to an existing plan that references the original
    story; otherwise creates a minimal new plan linking both.

    Args:
        original_story_id: The original story ID.
        follow_up_story_id: The newly created follow-up story ID.
        original_title: Human-readable title.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    plans_scope_dir = config.plans_dir / prefix
    plans_scope_dir.mkdir(parents=True, exist_ok=True)
    existing_plan = None
    if plans_scope_dir.exists():
        for plan_file in plans_scope_dir.glob("*.md"):
            try:
                if original_story_id in plan_file.read_text():
                    existing_plan = plan_file
                    break
            except Exception:
                continue
    if existing_plan:
        try:
            plan_content = existing_plan.read_text()
            append_text = (
                f"\n- {follow_up_story_id}: {original_title} "
                f"(Continuation — circuit breaker split)\n"
            )
            existing_plan.write_text(plan_content + append_text)
        except Exception as exc:
            logging.warning("Failed to update existing plan %s: %s", existing_plan, exc)
    else:
        plan_path = plans_scope_dir / f"{original_story_id}-plan.md"
        plan_content = f"""# Plan: {original_title}

## Stories

- {original_story_id}: {original_title} (partial — circuit breaker activated)
- {follow_up_story_id}: {original_title} (Continuation)

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
        try:
            plan_path.write_text(plan_content)
        except Exception as exc:
            logging.warning("Failed to create plan: %s", exc)


class CircuitBreaker:
    """Stateful circuit breaker tracking cumulative LOC across runbook steps.

    Usage::

        cb = CircuitBreaker()
        cb.record(step_loc)
        if cb.should_warn():
            ...
        if cb.should_halt():
            ...
    """

    def __init__(self) -> None:
        """Initialise with zero cumulative LOC."""
        self.cumulative_loc: int = 0

    def record(self, step_loc: int) -> None:
        """Add step_loc to cumulative total.

        Args:
            step_loc: Lines changed in the current step.
        """
        self.cumulative_loc += step_loc

    def should_warn(self) -> bool:
        """Return True when the warning threshold has been reached but not breached."""
        return LOC_WARNING_THRESHOLD <= self.cumulative_loc < LOC_CIRCUIT_BREAKER_THRESHOLD

    def should_halt(self) -> bool:
        """Return True when the circuit breaker threshold has been reached."""
        return self.cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD