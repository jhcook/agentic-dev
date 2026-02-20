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

"""Tests for INFRA-063: AI-Powered Journey Test Generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from agent.commands.journey import (
    _generate_ai_test,
    _generate_stub,
    _iter_eligible_journeys,
)
from agent.main import app

runner = CliRunner()

VALID_AI_CODE = '''\
import pytest


@pytest.mark.journey("JRN-100")
def test_jrn_100_step_1():
    """Step 1: do thing"""
    assert True
'''

INVALID_AI_CODE = "def test_broken(:\n    pass"  # SyntaxError


@pytest.fixture
def journey_tree(tmp_path):
    """Create a minimal journeys + tests tree for testing."""
    journeys = tmp_path / ".agent" / "cache" / "journeys" / "INFRA"
    journeys.mkdir(parents=True)
    tests_dir = tmp_path / "tests" / "journeys"
    tests_dir.mkdir(parents=True)
    # Create a source file for implementation.files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def main(): pass\n")
    return {
        "root": tmp_path,
        "journeys": journeys,
        "tests_dir": tests_dir,
        "src_dir": src_dir,
    }


def _write_journey(
    journeys_dir: Path,
    jid: str,
    state: str,
    tests: list | None = None,
    steps: list | None = None,
    impl_files: list | None = None,
):
    """Helper to write a journey YAML file."""
    data = {
        "id": jid,
        "title": f"Test Journey {jid}",
        "state": state,
        "actor": "developer",
        "description": "test",
        "steps": steps
        or [
            {
                "action": "do thing",
                "system_response": "ok",
                "assertions": ["it works"],
            },
        ],
        "acceptance_criteria": ["AC-1"],
        "error_paths": [{"trigger": "err", "expected": "handle"}],
        "edge_cases": [{"scenario": "edge", "expected": "handle"}],
    }
    if tests is not None:
        data.setdefault("implementation", {})["tests"] = tests
    if impl_files is not None:
        data.setdefault("implementation", {})["files"] = impl_files
    journeys_dir.joinpath(f"{jid}-test.yaml").write_text(
        yaml.dump(data, default_flow_style=False)
    )


# --- Helper unit tests ---


class TestIterEligibleJourneys:
    """Tests for _iter_eligible_journeys helper."""

    def test_returns_committed_without_tests(self, journey_tree):
        _write_journey(journey_tree["journeys"], "JRN-100", "COMMITTED")
        result = _iter_eligible_journeys(journey_tree["journeys"].parent)
        assert len(result) == 1
        assert result[0]["jid"] == "JRN-100"

    def test_filters_by_scope(self, journey_tree):
        _write_journey(journey_tree["journeys"], "JRN-100", "COMMITTED")
        # INFRA scope should match
        result = _iter_eligible_journeys(
            journey_tree["journeys"].parent, scope="INFRA"
        )
        assert len(result) == 1
        # MOBILE scope should not match
        result = _iter_eligible_journeys(
            journey_tree["journeys"].parent, scope="MOBILE"
        )
        assert len(result) == 0

    def test_filters_by_journey_id(self, journey_tree):
        _write_journey(journey_tree["journeys"], "JRN-100", "COMMITTED")
        _write_journey(journey_tree["journeys"], "JRN-101", "COMMITTED")
        result = _iter_eligible_journeys(
            journey_tree["journeys"].parent, journey_id="JRN-100"
        )
        assert len(result) == 1
        assert result[0]["jid"] == "JRN-100"


class TestGenerateStub:
    """Tests for _generate_stub helper."""

    def test_generates_valid_stub(self):
        data = {
            "steps": [
                {"action": "click button", "assertions": ["page loads"]},
            ]
        }
        result = _generate_stub(data, "JRN-100")
        assert 'pytest.mark.journey("JRN-100")' in result
        assert "test_jrn_100_step_1" in result
        assert 'pytest.skip("Not yet implemented")' in result
        assert "# page loads" in result


# --- AI generation tests (AC-1 through AC-12) ---


class TestGenerateAITest:
    """Tests for _generate_ai_test helper."""

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_ai_returns_valid_code_succeeds(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-1: AI returns valid code → returns test content."""
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do thing", "assertions": ["it works"]}],
            "implementation": {
                "files": ["src/app.py"],
            },
        }
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is not None
        assert "AI-generated regression tests" in result
        assert "JRN-100" in result

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_ai_syntax_error_returns_none(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-9/Neg: AI returns code with SyntaxError → returns None (fallback)."""
        mock_ai.complete.return_value = INVALID_AI_CODE
        data = {
            "steps": [{"action": "do thing", "assertions": ["it works"]}],
            "implementation": {"files": []},
        }
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is None

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_ai_service_exception_returns_none(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-8: AI service unavailable → returns None (fallback to stub)."""
        mock_ai.complete.side_effect = RuntimeError("Service unavailable")
        data = {
            "steps": [{"action": "do thing", "assertions": ["it works"]}],
            "implementation": {"files": []},
        }
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is None

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data")
    def test_scrub_called_on_source(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-5: scrub_sensitive_data() called on source context."""
        mock_scrub.return_value = "scrubbed"
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do", "assertions": ["ok"]}],
            "implementation": {"files": ["src/app.py"]},
        }
        _generate_ai_test(data, "JRN-100", journey_tree["root"])
        mock_scrub.assert_called()

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_source_context_truncated(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-5: Source context truncated at _MAX_SOURCE_CHARS budget."""
        # Write a large file
        big_content = "x" * 50_000
        (journey_tree["src_dir"] / "big.py").write_text(big_content)
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do", "assertions": ["ok"]}],
            "implementation": {"files": ["src/big.py"]},
        }
        _generate_ai_test(data, "JRN-100", journey_tree["root"])
        # Verify the prompt didn't include the full 50k chars
        call_args = mock_ai.complete.call_args
        user_prompt = call_args[0][1]
        assert len(user_prompt) < 50_000

    def test_zero_steps_returns_none(self, journey_tree):
        """Edge: Journey with 0 steps → skip AI, return None."""
        data = {"steps": [], "implementation": {"files": []}}
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is None

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_missing_impl_files_continues(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """Edge: Missing implementation.files path → warning, continue."""
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do", "assertions": ["ok"]}],
            "implementation": {"files": ["nonexistent/file.py"]},
        }
        # Should not raise, just warn and proceed
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is not None

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_license_header_present(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-10: Generated file has license header."""
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do", "assertions": ["ok"]}],
            "implementation": {"files": []},
        }
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is not None
        assert "Apache License" in result

    @patch("agent.core.ai.ai_service")
    @patch("agent.core.security.scrub_sensitive_data", side_effect=lambda x: x)
    def test_ai_docstring_present(
        self, mock_scrub, mock_ai, journey_tree
    ):
        """AC-10: Generated file has AI-specific docstring."""
        mock_ai.complete.return_value = VALID_AI_CODE
        data = {
            "steps": [{"action": "do", "assertions": ["ok"]}],
            "implementation": {"files": []},
        }
        result = _generate_ai_test(data, "JRN-100", journey_tree["root"])
        assert result is not None
        assert "AI-generated regression tests" in result


# --- CLI integration tests ---


class TestBackfillTestsAICLI:
    """Tests for `agent journey backfill-tests --ai` CLI flags."""

    @patch("agent.commands.journey._generate_ai_test")
    def test_ai_write_generates_file(self, mock_gen, journey_tree):
        """AC-1: --ai --write generates file."""
        mock_gen.return_value = VALID_AI_CODE
        _write_journey(
            journey_tree["journeys"], "JRN-100", "COMMITTED",
            impl_files=["src/app.py"],
        )

        with (
            patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent),
            patch("agent.core.config.config.repo_root", journey_tree["root"]),
        ):
            result = runner.invoke(
                app, ["journey", "backfill-tests", "--write"]
            )

        assert result.exit_code == 0
        stub = journey_tree["root"] / "tests" / "journeys" / "test_jrn_100.py"
        assert stub.exists()

    @patch("agent.commands.journey._generate_ai_test")
    def test_ai_dry_run_no_file(self, mock_gen, journey_tree):
        """AC-4: --ai --dry-run should preview but not write."""
        mock_gen.return_value = VALID_AI_CODE
        _write_journey(
            journey_tree["journeys"], "JRN-100", "COMMITTED",
            impl_files=["src/app.py"],
        )

        with (
            patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent),
            patch("agent.core.config.config.repo_root", journey_tree["root"]),
        ):
            result = runner.invoke(
                app, ["journey", "backfill-tests", "--dry-run"]
            )

        assert result.exit_code == 0
        stub = journey_tree["root"] / "tests" / "journeys" / "test_jrn_100.py"
        assert not stub.exists()

    @patch("agent.commands.journey._generate_ai_test", return_value=None)
    def test_ai_fallback_to_stub(self, mock_gen, journey_tree):
        """AC-8/9: AI failure → fallback to stub."""
        _write_journey(
            journey_tree["journeys"], "JRN-100", "COMMITTED",
            impl_files=["src/app.py"],
        )

        with (
            patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent),
            patch("agent.core.config.config.repo_root", journey_tree["root"]),
        ):
            result = runner.invoke(
                app, ["journey", "backfill-tests", "--write"]
            )

        assert result.exit_code == 0
        stub = journey_tree["root"] / "tests" / "journeys" / "test_jrn_100.py"
        assert stub.exists()
        content = stub.read_text()
        assert "Auto-generated test stubs" in content
        assert "AI fallbacks" in result.output

    def test_journey_flag_targets_single(self, journey_tree):
        """AC-7: --journey JRN-100 targets single journey."""
        _write_journey(journey_tree["journeys"], "JRN-100", "COMMITTED")
        _write_journey(journey_tree["journeys"], "JRN-101", "COMMITTED")

        with (
            patch("agent.core.config.config.journeys_dir", journey_tree["journeys"].parent),
            patch("agent.core.config.config.repo_root", journey_tree["root"]),
        ):
            result = runner.invoke(
                app,
                ["journey", "backfill-tests", "--journey", "JRN-100", "--write"],
            )

        assert result.exit_code == 0
        assert (journey_tree["root"] / "tests" / "journeys" / "test_jrn_100.py").exists()
        assert not (journey_tree["root"] / "tests" / "journeys" / "test_jrn_101.py").exists()
