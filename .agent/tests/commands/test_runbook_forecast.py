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

"""Tests for the INFRA-093 forecast gate in runbook generation."""

import pytest
from unittest.mock import patch

from agent.commands.runbook import score_story_complexity


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def complex_story():
    """Story that exceeds complexity thresholds (>8 steps, >4 files, refactor verb)."""
    return """\
# INFRA-999: Complex Story

## State

COMMITTED

## Implementation Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
- [ ] Step 4
- [ ] Step 5
- [ ] Step 6
- [ ] Step 7
- [ ] Step 8
- [ ] Step 9
- [ ] Step 10

#### [MODIFY] src/file1.py
#### [MODIFY] src/file2.py
#### [MODIFY] src/file3.py
#### [MODIFY] src/file4.py
#### [MODIFY] src/file5.py

Refactor the entire core module.
"""


@pytest.fixture
def simple_story():
    """Story that stays within complexity thresholds."""
    return """\
# INFRA-001: Simple Story

## State

COMMITTED

## Implementation Steps
- [ ] Step 1

#### [MODIFY] src/file1.py
"""


@pytest.fixture
def boundary_story():
    """Story at exact boundary values (8 steps, 4 files, 400 LOC) — should PASS."""
    return """\
# INFRA-002: Boundary Story

## State

COMMITTED

## Implementation Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
- [ ] Step 4
- [ ] Step 5
- [ ] Step 6
- [ ] Step 7
- [ ] Step 8

#### [MODIFY] src/a.py
#### [MODIFY] src/b.py
#### [MODIFY] src/c.py
#### [MODIFY] src/d.py

Implement the feature.
"""


@pytest.fixture
def migrate_story():
    """Story with 'migrate' verb for 2.0x intensity multiplier."""
    return """\
# INFRA-003: Migration Story

## State

COMMITTED

## Implementation Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

#### [MODIFY] src/a.py

Migrate the database schema.
"""


# ── score_story_complexity Tests ──────────────────────────────


def test_score_simple_story(simple_story):
    """Simple story scores well within all thresholds."""
    metrics = score_story_complexity(simple_story)
    assert metrics.step_count == 1
    assert metrics.file_count == 1
    assert metrics.verb_intensity == 1.0
    assert metrics.estimated_loc == 40.0


def test_score_complex_story(complex_story):
    """Complex story exceeds thresholds on steps, files, and LOC."""
    metrics = score_story_complexity(complex_story)
    assert metrics.step_count == 10
    assert metrics.file_count == 5
    assert metrics.verb_intensity == 1.5  # "refactor" keyword
    assert metrics.estimated_loc == (10 * 40) * 1.5  # 600


def test_score_boundary_story(boundary_story):
    """Boundary story is at exact limits — gate uses >, so this should PASS."""
    metrics = score_story_complexity(boundary_story)
    assert metrics.step_count == 8
    assert metrics.file_count == 4
    assert metrics.verb_intensity == 1.0  # "implement" is default
    assert metrics.estimated_loc == 320.0  # 8 * 40 * 1.0
    # All at or under limits — gate should NOT trigger
    assert metrics.estimated_loc <= 400
    assert metrics.step_count <= 8
    assert metrics.file_count <= 4


def test_score_migrate_verb_intensity(migrate_story):
    """'migrate' verb triggers 2.0x intensity multiplier."""
    metrics = score_story_complexity(migrate_story)
    assert metrics.verb_intensity == 2.0
    assert metrics.estimated_loc == (3 * 40) * 2.0  # 240


def test_score_empty_story():
    """Empty story produces zero scores."""
    metrics = score_story_complexity("")
    assert metrics.step_count == 0
    assert metrics.file_count == 0
    assert metrics.estimated_loc == 0.0


def test_score_context_width():
    """Context width counts ADR and JRN references."""
    content = "Uses ADR-005 and JRN-064 and ADR-010."
    metrics = score_story_complexity(content)
    assert metrics.context_width == 3


# ── log_skip_audit Tests ─────────────────────────────────────


def test_log_skip_audit_structured_output():
    """log_skip_audit emits structured audit dict with user, gate, resource."""
    from agent.commands.gates import log_skip_audit

    with patch("agent.commands.gates.logger.warning") as mock_log:
        with patch("getpass.getuser", return_value="testuser"):
            log_skip_audit("runbook_forecast", "INFRA-093")
            args, _ = mock_log.call_args
            assert "gate_bypass" in args[0]
            audit_data = args[1]
            assert audit_data["user"] == "testuser"
            assert audit_data["gate"] == "runbook_forecast"
            assert audit_data["resource"] == "INFRA-093"
            assert audit_data["action"] == "BYPASS"
            assert "timestamp" in audit_data


def test_log_skip_audit_backward_compatible():
    """Existing callers without resource_id still work (default empty string)."""
    from agent.commands.gates import log_skip_audit

    with patch("agent.commands.gates.logger.warning") as mock_log:
        with patch("getpass.getuser", return_value="testuser"):
            log_skip_audit("Security scan")
            args, _ = mock_log.call_args
            audit_data = args[1]
            assert audit_data["resource"] == ""
            assert audit_data["gate"] == "Security scan"