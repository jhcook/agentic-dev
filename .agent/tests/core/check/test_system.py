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

"""Unit tests for agent.core.check.system."""

from unittest.mock import patch

import pytest

from agent.core.check.system import check_credentials, validate_linked_journeys, validate_story


# ─── validate_linked_journeys ──────────────────────────────────────────────────


def test_validate_linked_journeys_valid(tmp_path):
    """Story with real JRN IDs passes."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "TEST").mkdir()
    (mock_stories / "TEST" / "TEST-001-example.md").write_text(
        "# Title\n\n## Linked Journeys\n\n- JRN-044 (User login)\n- JRN-053 (Coverage)\n\n## Impact Analysis Summary\n"
    )

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_linked_journeys("TEST-001")

    assert result["passed"] is True
    assert result["journey_ids"] == ["JRN-044", "JRN-053"]
    assert result["error"] is None


def test_validate_linked_journeys_placeholder(tmp_path):
    """Story with only JRN-XXX placeholder fails."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "TEST").mkdir()
    (mock_stories / "TEST" / "TEST-002-example.md").write_text(
        "# Title\n\n## Linked Journeys\n\n- JRN-XXX\n\n## Impact Analysis Summary\n"
    )

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_linked_journeys("TEST-002")

    assert result["passed"] is False
    assert "placeholder" in result["error"]


def test_validate_linked_journeys_missing_section(tmp_path):
    """Story without a Linked Journeys section at all fails."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "TEST").mkdir()
    (mock_stories / "TEST" / "TEST-004-example.md").write_text(
        "# Title\n\n## Problem Statement\n\n## Impact Analysis Summary\n"
    )

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_linked_journeys("TEST-004")

    assert result["passed"] is False
    assert "missing" in result["error"].lower()


def test_validate_linked_journeys_not_found(tmp_path):
    """Returns error dict (does not raise) when story file is absent."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_linked_journeys("NONEXISTENT-001")

    assert result["passed"] is False
    assert result["error"] is not None


# ─── validate_story ────────────────────────────────────────────────────────────


def test_validate_story_pass(tmp_path):
    """Full story with all required sections returns True when return_bool=True."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "INFRA").mkdir()
    (mock_stories / "INFRA" / "INFRA-001-test.md").write_text(
        "# Title\n\n"
        "## Problem Statement\n\n"
        "## User Story\n\n"
        "## Acceptance Criteria\n\n"
        "## Non-Functional Requirements\n\n"
        "## Impact Analysis Summary\n\n"
        "## Test Strategy\n\n"
        "## Rollback Plan\n"
    )

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_story("INFRA-001", return_bool=True)

    assert result is True


def test_validate_story_missing_sections(tmp_path):
    """Story missing sections returns False when return_bool=True."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()
    (mock_stories / "INFRA").mkdir()
    (mock_stories / "INFRA" / "INFRA-002-test.md").write_text(
        "# Title\n\n## Problem Statement\n"
    )

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_story("INFRA-002", return_bool=True)

    assert result is False


def test_validate_story_not_found_returns_false(tmp_path):
    """Missing story file returns False when return_bool=True (no exception)."""
    mock_stories = tmp_path / "stories"
    mock_stories.mkdir()

    with patch("agent.core.config.config.stories_dir", mock_stories):
        result = validate_story("INFRA-999", return_bool=True)

    assert result is False


# ─── check_credentials ────────────────────────────────────────────────────────


def test_check_credentials_delegates():
    """Delegates to validate_credentials without raising when mock succeeds."""
    with patch("agent.core.check.system.validate_credentials") as mock_vc:
        mock_vc.return_value = None
        check_credentials(check_llm=False)
        mock_vc.assert_called_once_with(check_llm=False)


def test_check_credentials_propagates_error():
    """Re-raises MissingCredentialsError from validate_credentials."""
    from agent.core.auth.errors import MissingCredentialsError

    with patch("agent.core.check.system.validate_credentials") as mock_vc:
        mock_vc.side_effect = MissingCredentialsError("No key")
        with pytest.raises(MissingCredentialsError):
            check_credentials(check_llm=True)