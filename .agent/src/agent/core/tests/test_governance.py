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

"""Regression suite for the agent.core.governance package facade (INFRA-101).

Ensures that all public symbols remain importable from the governance package
throughout the multi-slice decomposition (AC-4, AC-5, AC-6).
"""

import importlib


class TestPublicAPIAvailable:
    """All expected public symbols are importable from the governance package facade."""

    def test_import_load_roles(self) -> None:
        """load_roles is importable from the governance facade."""
        from agent.core.governance import load_roles  # noqa: F401
        assert callable(load_roles)

    def test_import_get_role(self) -> None:
        """get_role is importable from the governance facade."""
        from agent.core.governance import get_role  # noqa: F401
        assert callable(get_role)

    def test_import_log_governance_event(self) -> None:
        """log_governance_event is importable from the governance facade."""
        from agent.core.governance import log_governance_event  # noqa: F401
        assert callable(log_governance_event)

    def test_import_convene_council_full(self) -> None:
        """convene_council_full is importable from the governance facade."""
        from agent.core.governance import convene_council_full  # noqa: F401
        assert callable(convene_council_full)

    def test_import_audit_result(self) -> None:
        """AuditResult dataclass is importable from the governance facade."""
        from agent.core.governance import AuditResult  # noqa: F401
        assert AuditResult is not None

    def test_import_extract_references(self) -> None:
        """_extract_references is importable from the governance facade."""
        from agent.core.governance import _extract_references  # noqa: F401
        assert callable(_extract_references)

    def test_import_validate_references(self) -> None:
        """_validate_references is importable from the governance facade."""
        from agent.core.governance import _validate_references  # noqa: F401
        assert callable(_validate_references)

    def test_import_run_audit(self) -> None:
        """run_audit is importable from the governance facade."""
        from agent.core.governance import run_audit  # noqa: F401
        assert callable(run_audit)

    def test_no_circular_import(self) -> None:
        """Importing agent.cli succeeds with no circular import errors (AC-6)."""
        mod = importlib.import_module("agent.cli")
        assert mod is not None


class TestLoadRolesBehavioralEquivalence:
    """Behavioral equivalence checks for load_roles() via the facade (AC-5)."""

    def test_returns_non_empty_list(self) -> None:
        """load_roles() returns a non-empty list of role dicts."""
        from agent.core.governance import load_roles
        roles = load_roles()
        assert isinstance(roles, list)
        assert len(roles) > 0

    def test_each_role_has_name_and_focus(self) -> None:
        """Every role dict returned by load_roles() has 'name' and 'focus' keys."""
        from agent.core.governance import load_roles
        roles = load_roles()
        for role in roles:
            assert "name" in role, f"Role missing 'name': {role}"
            assert "focus" in role, f"Role missing 'focus': {role}"
