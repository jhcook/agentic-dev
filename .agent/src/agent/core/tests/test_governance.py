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

"""Regression suite for agent.core.governance package facade (INFRA-101).

Ensures that all public symbols remain importable from the governance package
throughout the multi-slice decomposition (AC-4, AC-5, AC-6).
"""

import importlib


class TestPublicAPIAvailable:
    """All public symbols are importable from agent.core.governance."""

    def test_import_load_roles(self) -> None:
        """Verify load_roles is available."""
        from agent.core.governance import load_roles  # noqa: F401
        assert callable(load_roles)

    def test_import_log_governance_event(self) -> None:
        """Verify log_governance_event is available."""
        from agent.core.governance import log_governance_event  # noqa: F401
        assert callable(log_governance_event)

    def test_import_convene_council_full(self) -> None:
        """Verify convene_council_full is available."""
        from agent.core.governance import convene_council_full  # noqa: F401
        assert callable(convene_council_full)

    def test_import_audit_result(self) -> None:
        """Verify AuditResult is available."""
        from agent.core.governance import AuditResult  # noqa: F401
        assert AuditResult is not None

    def test_import_extract_references(self) -> None:
        """Verify _extract_references is available."""
        from agent.core.governance import _extract_references  # noqa: F401
        assert callable(_extract_references)

    def test_import_validate_references(self) -> None:
        """Verify _validate_references is available."""
        from agent.core.governance import _validate_references  # noqa: F401
        assert callable(_validate_references)

    def test_import_run_audit(self) -> None:
        """Verify run_audit is available."""
        from agent.core.governance import run_audit  # noqa: F401
        assert callable(run_audit)

    def test_no_circular_import(self) -> None:
        """python -c 'import agent.cli' must succeed (AC-6)."""
        # Exercise the full import chain by importing the CLI module
        mod = importlib.import_module("agent.cli")
        assert mod is not None


class TestLoadRolesBehavioralEquivalence:
    """load_roles() returns a list of dicts with expected keys."""

    def test_returns_list(self) -> None:
        """load_roles returns a list."""
        from agent.core.governance import load_roles
        roles = load_roles()
        assert isinstance(roles, list)
        assert len(roles) > 0

    def test_each_role_has_required_keys(self) -> None:
        """Each role dict contains the expected keys."""
        from agent.core.governance import load_roles
        roles = load_roles()
        for role in roles:
            assert "name" in role
            assert "focus" in role