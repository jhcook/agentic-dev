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

"""Unit tests for agent.core.governance.roles (INFRA-101).

Covers:
  - load_roles: successful load from valid agents.yaml
  - load_roles: fallback when agents.yaml is missing
  - load_roles: fallback when agents.yaml is malformed YAML
  - load_roles: fallback when agents.yaml has empty team
  - get_role: lookup by name and by @Handle
  - get_role: returns None for unknown names
"""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.governance.roles import _DEFAULT_ROLES, get_role, load_roles


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _write_agents_yaml(tmp_path: Path, content: str) -> Path:
    """Write content to a temporary agents.yaml and return the path."""
    p = tmp_path / "agents.yaml"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# load_roles — happy path
# ---------------------------------------------------------------------------

class TestLoadRolesHappyPath:
    """Tests for load_roles() when agents.yaml is valid and present."""

    def test_returns_list_of_dicts(self, tmp_path: Path) -> None:
        """load_roles returns a list of dicts parsed from valid YAML."""
        yaml_content = textwrap.dedent("""\
            team:
              - name: Architect
                role: architect
                description: System design and ADR compliance.
                responsibilities:
                  - scalability
                  - patterns
                governance_checks: []
                instruction: ""
        """)
        _write_agents_yaml(tmp_path, yaml_content)

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert isinstance(roles, list)
        assert len(roles) == 1
        role = roles[0]
        assert role["name"] == "Architect"
        assert role["role"] == "architect"
        assert "scalability" in role["focus"]

    def test_focus_concatenates_responsibilities(self, tmp_path: Path) -> None:
        """focus field joins description and responsibilities into one string."""
        yaml_content = textwrap.dedent("""\
            team:
              - name: QA
                role: qa
                description: Test coverage.
                responsibilities:
                  - edge cases
                  - testability
        """)
        _write_agents_yaml(tmp_path, yaml_content)

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert "edge cases" in roles[0]["focus"]
        assert "testability" in roles[0]["focus"]

    def test_role_key_defaults_to_lowercase_name(self, tmp_path: Path) -> None:
        """role key defaults to name.lower() when not explicitly provided."""
        yaml_content = textwrap.dedent("""\
            team:
              - name: Security
                description: Security checks.
        """)
        _write_agents_yaml(tmp_path, yaml_content)

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert roles[0]["role"] == "security"

    def test_all_required_keys_present(self, tmp_path: Path) -> None:
        """Every returned role dict has the required six keys."""
        yaml_content = textwrap.dedent("""\
            team:
              - name: Docs
                role: docs
                description: Docs quality.
        """)
        _write_agents_yaml(tmp_path, yaml_content)

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        required_keys = {"name", "role", "description", "focus", "governance_checks", "instruction"}
        assert set(roles[0].keys()) >= required_keys


# ---------------------------------------------------------------------------
# load_roles — fallback paths (AC: negative test)
# ---------------------------------------------------------------------------

class TestLoadRolesFallback:
    """Tests for load_roles() graceful degradation to default panel."""

    def test_fallback_when_file_missing(self, tmp_path: Path) -> None:
        """Returns default roles when agents.yaml does not exist."""
        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path  # agents.yaml absent
            roles = load_roles()

        assert roles == list(_DEFAULT_ROLES)

    def test_fallback_when_yaml_malformed(self, tmp_path: Path) -> None:
        """Returns default roles when agents.yaml contains invalid YAML."""
        _write_agents_yaml(tmp_path, "team: [invalid: yaml: :")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert roles == list(_DEFAULT_ROLES)

    def test_fallback_when_team_key_missing(self, tmp_path: Path) -> None:
        """Returns default roles when agents.yaml has no 'team' key."""
        _write_agents_yaml(tmp_path, "config:\n  key: value\n")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert roles == list(_DEFAULT_ROLES)

    def test_fallback_when_team_is_empty_list(self, tmp_path: Path) -> None:
        """Returns default roles when agents.yaml team is an empty list."""
        _write_agents_yaml(tmp_path, "team: []\n")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert roles == list(_DEFAULT_ROLES)

    def test_fallback_logs_warning_on_parse_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """load_roles emits a WARNING when YAML is malformed (not silent)."""
        import logging

        _write_agents_yaml(tmp_path, "team: [invalid: yaml: :")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            with caplog.at_level(logging.WARNING, logger="agent.core.governance.roles"):
                load_roles()

        assert any("Failed to parse" in r.message for r in caplog.records)

    def test_default_panel_has_nine_roles(self, tmp_path: Path) -> None:
        """Default fallback panel contains the expected 9 governance roles."""
        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert len(roles) == 9


# ---------------------------------------------------------------------------
# get_role
# ---------------------------------------------------------------------------

class TestGetRole:
    """Tests for get_role() persona resolution."""

    _ROLES = [
        {"name": "Architect", "role": "architect", "focus": "Design"},
        {"name": "Security (CISO)", "role": "security", "focus": "Security"},
    ]

    def test_lookup_by_full_name(self) -> None:
        """get_role finds a role by its full name (case-insensitive)."""
        result = get_role("Architect", self._ROLES)
        assert result is not None
        assert result["role"] == "architect"

    def test_lookup_by_at_handle(self) -> None:
        """get_role strips leading @ from handle before matching."""
        result = get_role("@Architect", self._ROLES)
        assert result is not None
        assert result["role"] == "architect"

    def test_lookup_by_role_key(self) -> None:
        """get_role finds a role by its role key (not just name)."""
        result = get_role("security", self._ROLES)
        assert result is not None
        assert result["name"] == "Security (CISO)"

    def test_returns_none_for_unknown_name(self) -> None:
        """get_role returns None for an unrecognised role name."""
        result = get_role("NonExistent", self._ROLES)
        assert result is None

    def test_case_insensitive_name_match(self) -> None:
        """get_role name lookup is case-insensitive."""
        result = get_role("ARCHITECT", self._ROLES)
        assert result is not None
