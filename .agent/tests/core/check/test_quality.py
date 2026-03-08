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

"""Unit tests for agent.core.check.quality."""

import pytest

from agent.core.check.quality import check_journey_coverage


# ─── check_journey_coverage ───────────────────────────────────────────────────


def test_journey_coverage_no_dir(tmp_path):
    """Returns passed=True when journeys directory does not exist (negative test from AC)."""
    non_existent = tmp_path / "no_journeys"
    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is True
    assert result["total"] == 0
    assert result["linked"] == 0
    assert result["missing"] == 0
    assert result["warnings"] == []
    assert result["missing_ids"] == []


def test_journey_coverage_all_linked(tmp_path):
    """All committed journeys have existing test files → passed=True."""
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys" / "SCOPE"
    journeys_dir.mkdir(parents=True)

    test_file = tmp_path / "tests" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("# test")

    yaml_content = (
        "id: JRN-001\n"
        "state: COMMITTED\n"
        "title: Example\n"
        "implementation:\n"
        "  tests:\n"
        f"  - tests/test_foo.py\n"
    )
    (journeys_dir / "JRN-001.yaml").write_text(yaml_content)

    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is True
    assert result["total"] == 1
    assert result["linked"] == 1
    assert result["missing"] == 0
    assert result["warnings"] == []


def test_journey_coverage_missing_tests(tmp_path):
    """Committed journey with no test links → passed=False."""
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys" / "SCOPE"
    journeys_dir.mkdir(parents=True)

    yaml_content = (
        "id: JRN-002\n"
        "state: COMMITTED\n"
        "title: Example\n"
        "implementation:\n"
        "  tests: []\n"
    )
    (journeys_dir / "JRN-002.yaml").write_text(yaml_content)

    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is False
    assert result["missing"] == 1
    assert "JRN-002" in result["missing_ids"]
    assert any("No tests linked" in w for w in result["warnings"])


def test_journey_coverage_draft_ignored(tmp_path):
    """DRAFT journeys are excluded from coverage checks."""
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys" / "SCOPE"
    journeys_dir.mkdir(parents=True)

    yaml_content = (
        "id: JRN-003\n"
        "state: DRAFT\n"
        "title: Draft journey\n"
        "implementation:\n"
        "  tests: []\n"
    )
    (journeys_dir / "JRN-003.yaml").write_text(yaml_content)

    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is True
    assert result["total"] == 0


def test_journey_coverage_missing_file(tmp_path):
    """Journey whose test file does not exist → passed=False."""
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys" / "SCOPE"
    journeys_dir.mkdir(parents=True)

    yaml_content = (
        "id: JRN-004\n"
        "state: COMMITTED\n"
        "title: Example\n"
        "implementation:\n"
        "  tests:\n"
        "  - tests/ghost_test.py\n"
    )
    (journeys_dir / "JRN-004.yaml").write_text(yaml_content)

    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is False
    assert "JRN-004" in result["missing_ids"]
    assert any("Test file not found" in w for w in result["warnings"])


def test_journey_coverage_absolute_path_warning(tmp_path):
    """Absolute test path is flagged as a warning and marked missing."""
    journeys_dir = tmp_path / ".agent" / "cache" / "journeys" / "SCOPE"
    journeys_dir.mkdir(parents=True)

    yaml_content = (
        "id: JRN-005\n"
        "state: COMMITTED\n"
        "title: Example\n"
        "implementation:\n"
        "  tests:\n"
        "  - /absolute/path/test.py\n"
    )
    (journeys_dir / "JRN-005.yaml").write_text(yaml_content)

    result = check_journey_coverage(repo_root=tmp_path)

    assert result["passed"] is False
    assert any("Absolute test path" in w for w in result["warnings"])