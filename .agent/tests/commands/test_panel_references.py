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

"""Integration tests for INFRA-060 panel reference anchoring in convene_council_full."""

from unittest.mock import patch

import pytest

from agent.core.governance import convene_council_full


@pytest.fixture
def mock_ai_service():
    with patch("agent.core.governance.ai_service") as mock:
        mock.provider = "openai"
        yield mock


def test_gatekeeper_references_in_json_report(mock_ai_service, tmp_path):
    """Gatekeeper mode should extract, validate, and include references in json_report."""
    mock_ai_service.complete.return_value = (
        "VERDICT: PASS\n"
        "SUMMARY: Compliant with ADR-001.\n"
        "FINDINGS:\n- Follows ADR-001 architecture.\n"
        "REFERENCES:\n- ADR-001\n"
        "REQUIRED_CHANGES:\n"
    )

    # Create a valid ADR file
    with patch("agent.core.governance.config") as mock_config:
        mock_config.agent_dir = tmp_path
        mock_config.adrs_dir = tmp_path / "adrs"
        mock_config.adrs_dir.mkdir()
        (mock_config.adrs_dir / "ADR-001-test.md").write_text("# ADR-001")
        mock_config.journeys_dir = tmp_path / "journeys"
        mock_config.journeys_dir.mkdir()
        mock_config.repo_root = tmp_path
        mock_config.get_council_tools.return_value = []

        # Mock load_roles to return a single role
        with patch("agent.core.governance.load_roles") as mock_roles:
            mock_roles.return_value = [{"name": "architect", "focus": "Architecture"}]

            result = convene_council_full(
                story_id="TEST-1",
                story_content="Story",
                rules_content="Rules",
                instructions_content="",
                full_diff="diff --git a/test.py",
                mode="gatekeeper",
                adrs_content="ADR-001: Test decision",
            )

    assert result["verdict"] == "PASS"
    roles = result["json_report"]["roles"]
    assert len(roles) == 1
    refs = roles[0].get("references", {})
    assert "ADR-001" in refs.get("valid", [])
    assert refs.get("invalid", []) == []

    # Check aggregate metrics
    metrics = result["json_report"].get("reference_metrics", {})
    assert metrics["total_refs"] >= 1
    assert metrics["citation_rate"] > 0


def test_consultative_references_extracted(mock_ai_service, tmp_path):
    """Consultative mode should also extract references from free-text AI output."""
    mock_ai_service.complete.return_value = (
        "Based on ADR-001 and JRN-045, I recommend the following changes..."
    )

    with patch("agent.core.governance.config") as mock_config:
        mock_config.agent_dir = tmp_path
        mock_config.adrs_dir = tmp_path / "adrs"
        mock_config.adrs_dir.mkdir()
        (mock_config.adrs_dir / "ADR-001-test.md").write_text("# ADR-001")
        mock_config.journeys_dir = tmp_path / "journeys"
        scope = mock_config.journeys_dir / "INFRA"
        scope.mkdir(parents=True)
        (scope / "JRN-045-test.yaml").write_text("id: JRN-045")
        mock_config.repo_root = tmp_path
        mock_config.get_council_tools.return_value = []

        with patch("agent.core.governance.load_roles") as mock_roles:
            mock_roles.return_value = [{"name": "architect", "focus": "Architecture"}]

            result = convene_council_full(
                story_id="TEST-1",
                story_content="Story",
                rules_content="Rules",
                instructions_content="",
                full_diff="diff --git a/test.py",
                mode="consultative",
                adrs_content="ADR-001: Test",
            )

    roles = result["json_report"]["roles"]
    refs = roles[0].get("references", {})
    assert "ADR-001" in refs.get("valid", [])
    assert "JRN-045" in refs.get("valid", [])


def test_invalid_reference_warning(mock_ai_service, tmp_path):
    """Invalid references should be flagged and tracked in metrics."""
    mock_ai_service.complete.return_value = (
        "VERDICT: PASS\n"
        "SUMMARY: See ADR-999.\n"
        "FINDINGS:\n- Per ADR-999 guidelines.\n"
        "REFERENCES:\n- ADR-999\n"
    )

    warnings = []

    def capture_callback(msg):
        warnings.append(msg)

    with patch("agent.core.governance.config") as mock_config:
        mock_config.agent_dir = tmp_path
        mock_config.adrs_dir = tmp_path / "adrs"
        mock_config.adrs_dir.mkdir()  # No ADR-999 file
        mock_config.journeys_dir = tmp_path / "journeys"
        mock_config.journeys_dir.mkdir()
        mock_config.repo_root = tmp_path
        mock_config.get_council_tools.return_value = []

        with patch("agent.core.governance.load_roles") as mock_roles:
            mock_roles.return_value = [{"name": "security", "focus": "Security"}]

            result = convene_council_full(
                story_id="TEST-1",
                story_content="Story",
                rules_content="Rules",
                instructions_content="",
                full_diff="diff --git a/test.py",
                mode="gatekeeper",
                progress_callback=capture_callback,
            )

    # Check the invalid ref was caught
    roles = result["json_report"]["roles"]
    refs = roles[0].get("references", {})
    assert "ADR-999" in refs.get("invalid", [])

    # Check warning was emitted
    assert any("ADR-999" in w and "does not exist" in w for w in warnings)

    # Check hallucination rate
    metrics = result["json_report"].get("reference_metrics", {})
    assert metrics["hallucination_rate"] > 0
