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

"""Tests for INFRA-058: Journey-Linked Regression Tests."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from agent.commands.check import check_journey_coverage
from agent.main import app

runner = CliRunner()


@pytest.fixture
def journey_tree(tmp_path):
    """Create a minimal journeys + tests tree for testing."""
    journeys = tmp_path / ".agent" / "cache" / "journeys" / "INFRA"
    journeys.mkdir(parents=True)
    tests_dir = tmp_path / "tests" / "journeys"
    tests_dir.mkdir(parents=True)
    return {
        "root": tmp_path,
        "journeys": journeys,
        "tests_dir": tests_dir,
    }


def _write_journey(journeys_dir: Path, jid: str, state: str, tests: list | None = None):
    """Helper to write a journey YAML file."""
    data = {
        "id": jid,
        "title": f"Test Journey {jid}",
        "state": state,
        "actor": "developer",
        "description": "test",
        "steps": [
            {"action": "do thing", "system_response": "ok", "assertions": ["it works"]},
        ],
        "acceptance_criteria": ["AC-1"],
        "error_paths": [{"trigger": "err", "expected": "handle"}],
        "edge_cases": [{"scenario": "edge", "expected": "handle"}],
    }
    if tests is not None:
        data["implementation"] = {"tests": tests}
    journeys_dir.joinpath(f"{jid}-test.yaml").write_text(
        yaml.dump(data, default_flow_style=False)
    )


# --- AC-1: COMMITTED journeys require non-empty tests ---

class TestValidateJourneyTestEnforcement:
    """Tests for validate_journey state-aware test enforcement."""

    def test_committed_no_tests_fails(self, journey_tree):
        """AC-1: COMMITTED journey without tests should fail validation."""
        _write_journey(journey_tree["journeys"], "JRN-901", "COMMITTED", tests=[])
        jfile = journey_tree["journeys"] / "JRN-901-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 1
        assert "implementation.tests" in result.output

    def test_committed_with_valid_tests_passes(self, journey_tree):
        """AC-1: COMMITTED journey with valid test files should pass."""
        test_file = journey_tree["tests_dir"] / "test_jrn_902.py"
        test_file.write_text("def test_it(): pass\n")
        rel = str(test_file.relative_to(journey_tree["root"]))

        _write_journey(journey_tree["journeys"], "JRN-902", "COMMITTED", tests=[rel])
        jfile = journey_tree["journeys"] / "JRN-902-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 0

    def test_draft_no_tests_passes(self, journey_tree):
        """AC-9: DRAFT journey without tests should pass (no enforcement)."""
        _write_journey(journey_tree["journeys"], "JRN-903", "DRAFT", tests=[])
        jfile = journey_tree["journeys"] / "JRN-903-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 0


# --- AC-2: Reject invalid paths ---

class TestValidateJourneyPathSecurity:
    """Tests for path validation in validate_journey."""

    def test_absolute_path_rejected(self, journey_tree):
        """AC-2: Absolute test paths should be rejected."""
        _write_journey(
            journey_tree["journeys"], "JRN-904", "COMMITTED",
            tests=["/etc/passwd"],
        )
        jfile = journey_tree["journeys"] / "JRN-904-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 1
        assert "must be relative" in result.output

    def test_traversal_path_rejected(self, journey_tree):
        """AC-2: Path traversal should be rejected."""
        _write_journey(
            journey_tree["journeys"], "JRN-905", "COMMITTED",
            tests=["../../etc/passwd"],
        )
        jfile = journey_tree["journeys"] / "JRN-905-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 1
        assert "escapes project root" in result.output

    def test_missing_file_rejected(self, journey_tree):
        """AC-2: Non-existent test files should be rejected."""
        _write_journey(
            journey_tree["journeys"], "JRN-906", "COMMITTED",
            tests=["tests/journeys/test_does_not_exist.py"],
        )
        jfile = journey_tree["journeys"] / "JRN-906-test.yaml"

        with patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["validate-journey", str(jfile)])

        assert result.exit_code == 1
        assert "not found" in result.output


# --- AC-3/7: check_journey_coverage function ---

class TestCheckJourneyCoverage:
    """Tests for the check_journey_coverage standalone function."""

    def test_empty_directory(self, journey_tree):
        """No journeys → passes with zero counts."""
        result = check_journey_coverage(journey_tree["root"])
        assert result["passed"] is True
        assert result["total"] == 0

    def test_all_linked(self, journey_tree):
        """All COMMITTED journeys have valid test files → full coverage."""
        test_file = journey_tree["tests_dir"] / "test_all.py"
        test_file.write_text("pass\n")
        rel = str(test_file.relative_to(journey_tree["root"]))
        _write_journey(journey_tree["journeys"], "JRN-910", "COMMITTED", tests=[rel])

        result = check_journey_coverage(journey_tree["root"])
        assert result["total"] == 1
        assert result["linked"] == 1
        assert result["missing"] == 0
        assert result["warnings"] == []

    def test_missing_tests(self, journey_tree):
        """COMMITTED journey with no tests → warning."""
        _write_journey(journey_tree["journeys"], "JRN-911", "COMMITTED", tests=[])

        result = check_journey_coverage(journey_tree["root"])
        assert result["total"] == 1
        assert result["missing"] == 1
        assert any("No tests linked" in w for w in result["warnings"])

    def test_draft_ignored(self, journey_tree):
        """DRAFT journeys are excluded from coverage counts."""
        _write_journey(journey_tree["journeys"], "JRN-912", "DRAFT", tests=[])

        result = check_journey_coverage(journey_tree["root"])
        assert result["total"] == 0

    def test_missing_file_warning(self, journey_tree):
        """COMMITTED with non-existent test file → warning about missing file."""
        _write_journey(
            journey_tree["journeys"], "JRN-913", "COMMITTED",
            tests=["tests/journeys/ghost.py"],
        )

        result = check_journey_coverage(journey_tree["root"])
        assert result["missing"] == 1
        assert any("not found" in w for w in result["warnings"])


# --- AC-4: coverage CLI command ---

class TestCoverageCLI:
    """Tests for `agent journey coverage` command."""

    def test_coverage_table_output(self, journey_tree):
        """Coverage command should produce a table."""
        test_file = journey_tree["tests_dir"] / "test_j.py"
        test_file.write_text("pass\n")
        rel = str(test_file.relative_to(journey_tree["root"]))
        _write_journey(journey_tree["journeys"], "JRN-920", "COMMITTED", tests=[rel])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "coverage"])

        assert result.exit_code == 0
        assert "JRN-920" in result.output
        assert "Coverage:" in result.output

    def test_coverage_json_output(self, journey_tree):
        """Coverage --json should produce JSON."""
        _write_journey(journey_tree["journeys"], "JRN-921", "COMMITTED", tests=[])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "coverage", "--json"])

        assert result.exit_code == 0
        assert "JRN-921" in result.output


# --- AC-6: backfill-tests CLI command ---

class TestBackfillTestsCLI:
    """Tests for `agent journey backfill-tests` command."""

    def test_backfill_generates_stubs(self, journey_tree):
        """Backfill should generate test stubs for COMMITTED journeys without tests."""
        _write_journey(journey_tree["journeys"], "JRN-930", "COMMITTED", tests=[])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "backfill-tests"])

        assert result.exit_code == 0
        assert "Generated" in result.output

        stub = journey_tree["root"] / "tests" / "journeys" / "test_jrn_930.py"
        assert stub.exists()
        content = stub.read_text()
        assert "JRN-930" in content
        assert "pytest.mark.journey" in content

    def test_backfill_dry_run(self, journey_tree):
        """Backfill --dry-run should not write files."""
        _write_journey(journey_tree["journeys"], "JRN-931", "COMMITTED", tests=[])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "backfill-tests", "--dry-run"])

        assert result.exit_code == 0
        assert "Would" in result.output

        stub = journey_tree["root"] / "tests" / "journeys" / "test_jrn_931.py"
        assert not stub.exists()

    def test_backfill_skips_draft(self, journey_tree):
        """Backfill should skip DRAFT journeys."""
        _write_journey(journey_tree["journeys"], "JRN-932", "DRAFT", tests=[])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "backfill-tests"])

        assert result.exit_code == 0
        assert "0 test stub" in result.output

    def test_backfill_skips_already_linked(self, journey_tree):
        """Backfill should skip journeys that already have tests."""
        test_file = journey_tree["tests_dir"] / "test_existing.py"
        test_file.write_text("pass\n")
        rel = str(test_file.relative_to(journey_tree["root"]))
        _write_journey(journey_tree["journeys"], "JRN-933", "COMMITTED", tests=[rel])

        with patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent), \
             patch("agent.core.config.config.repo_root", journey_tree["root"]):
            result = runner.invoke(app, ["journey", "backfill-tests"])

        assert result.exit_code == 0
        assert "0 test stub" in result.output
