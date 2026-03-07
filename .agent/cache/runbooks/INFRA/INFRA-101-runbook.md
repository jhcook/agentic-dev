# INFRA-101: Decompose Governance Module

## State

ACCEPTED

## Goal Description

Decompose the monolithic `core/governance.py` (1,989 LOC, three distinct concerns) into a proper Python package `core/governance/` with focused sub-modules: `roles.py` (persona/role management), `validation.py` (preflight/audit logging), and `panel.py` (council orchestration). A facade `__init__.py` re-exports all public symbols so no callers change. This satisfies ADR-041's 500 LOC ceiling and enables independent testing of each concern.

> **Scope note**: The `agent new-runbook` forecast gate estimated ~600 LOC / 10 steps and rejected the full story in one pass. The auto-generated decomposition plan at `.agent/cache/plans/INFRA/INFRA-101-plan.md` breaks this into 5 child slices. **This runbook implements slices 1 and 5** — package scaffold + roles extraction + the `__init__.py` facade — which are safe to land together (~300 LOC, low regression risk). Slices 2–4 (validation, panel-prompts, panel execution) will follow as INFRA-101.2 through INFRA-101.4.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-036: Preflight Governance Check

## Panel Review Findings

### @Architect
The decomposition order matters. `roles.py` must be extracted first because it has zero dependencies on the rest of `governance.py`. The `__init__.py` facade must be created immediately alongside it so callers never see a broken import state mid-refactor. The remaining sub-modules (`validation.py`, `panel.py`) can be extracted in subsequent stories once the package boundary is established and clean.

Critical: the facade `__init__.py` must import **all currently-exported symbols** from `governance.py` from day one — even those still living in `governance.py` until later slices complete.

### @Security
`load_roles` reads from `agents.yaml` via `yaml.safe_load` (safe). The `except Exception: pass` fallback silently swallows YAML parse errors — the new module should log a structured warning instead. No PII risk in role data.

### @QA
The story requires `tests/core/test_governance.py` to pass without modification (AC-5). Since that file does not yet exist, new tests must be added that cover: (a) successful load from a valid `agents.yaml`, (b) fallback when file is missing, (c) fallback when YAML is malformed. A `tests/core/governance/` package with `__init__.py` must be created.

### @Compliance
No SOC2 audit fields are touched in this slice (audit logging stays in `governance.py` until slice 2). No risk.

### @Observability
The `except Exception: pass` in `load_roles` must be upgraded to `logger.warning(...)` in the extracted module to ensure YAML parse failures are observable.

## Codebase Introspection

### Target File Signatures (from source)

From `.agent/src/agent/core/governance.py`:

```
L56:  def load_roles() -> List[Dict[str, str]]:
         # Reads .agent/etc/agents.yaml, returns list of role dicts.
         # Fallback: returns 9 hardcoded roles if file missing/invalid.
         # Called by: convene_council_full (governance.py:1158), check.py:32

L44:  AUDIT_LOG_FILE = config.agent_dir / "logs" / "audit_events.log"

# Public symbols currently exported (all callers use these):
#   audit.py:22  -> run_audit, log_governance_event
#   check.py:32  -> convene_council_full
#   orchestrator.py:280 -> _validate_finding_against_source, _validate_references, _extract_references
#   formatters.py:15 -> AuditResult
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `agent/core/tests/test_security.py` | `agent.core.governance` (indirect) | unchanged | No action |
| `agent/core/governance/test_roles.py` (NEW) | N/A | `agent.core.governance.roles` | Create |
| `agent/core/tests/test_governance.py` (NEW) | N/A | `agent.core.governance` (facade) | Create |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `load_roles()` returns `List[Dict]` with keys `role`, `name`, `description`, `focus`, `governance_checks`, `instruction` | `governance.py:78-84` | yes | ✅ Yes |
| Fallback returns 9 hardcoded roles | `governance.py:89-100` | yes | ✅ Yes |
| `from agent.core.governance import convene_council_full` works | all callers | yes | ✅ Yes (via `__init__.py`) |
| `from agent.core.governance import AuditResult` works | `formatters.py:15` | yes | ✅ Yes (via `__init__.py`) |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Upgrade `except Exception: pass` in `load_roles` to `logger.warning(...)` in the new module (observability improvement — safe, no interface change).

## Implementation Steps

### Step 0: Pre-create the package directory tree

Run this once before any file steps. Creates `governance/`
so the CLI never needs to search for an ambiguous "governance" directory.

```bash
mkdir -p .agent/src/agent/core/governance && mkdir -p .agent/tests/core/governance
```

### Step 1: Create the `core/governance/` package directory with `__init__.py` facade

The `__init__.py` re-exports **all current public symbols** from `governance.py` so no callers break during the multi-slice migration.

#### [NEW] .agent/src/agent/core/governance/**init**.py

```python
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

"""Governance package facade.

Re-exports all public symbols from the governance sub-modules so that
existing callers using ``from agent.core.governance import ...`` continue
to work without modification throughout the multi-slice decomposition.

Decomposition status:
  - roles.py      ✅ Extracted (INFRA-101)
  - validation.py ⏳ Pending (INFRA-101.2)
  - panel.py      ⏳ Pending (INFRA-101.4)
"""

# ── Roles sub-module (INFRA-101) ──────────────────────────────────────────
from agent.core.governance.roles import (
    load_roles,
)

# ── Remaining symbols still in the legacy monolith (until extracted) ───────
# These re-exports keep all callers working while the decomposition proceeds.
from agent.core._governance_legacy import (  # noqa: F401
    AUDIT_LOG_FILE,
    ROLE_FILE_PATTERNS,
    AuditResult,
    log_governance_event,
    convene_council,
    convene_council_full,
    _parse_findings,
    _parse_bullet_list,
    _extract_references,
    _validate_references,
    _filter_relevant_roles,
    _build_file_context,
    _line_in_diff_hunk,
    _validate_finding_against_source,
    _resolve_file_path,
    is_governed,
    find_stagnant_files,
    find_orphaned_artifacts,
    run_audit,
    check_license_headers,
)

__all__ = [
    # Roles
    "load_roles",
    # Legacy (re-exported until extraction complete)
    "AUDIT_LOG_FILE",
    "ROLE_FILE_PATTERNS",
    "AuditResult",
    "log_governance_event",
    "convene_council",
    "convene_council_full",
    "_parse_findings",
    "_parse_bullet_list",
    "_extract_references",
    "_validate_references",
    "_filter_relevant_roles",
    "_build_file_context",
    "_line_in_diff_hunk",
    "_validate_finding_against_source",
    "_resolve_file_path",
    "is_governed",
    "find_stagnant_files",
    "find_orphaned_artifacts",
    "run_audit",
    "check_license_headers",
]
```

### Step 2: Rename `governance.py` to `_governance_legacy.py` using git mv

The legacy monolith is renamed with a leading underscore to mark it as internal-only. `git mv` preserves history. The file content is unchanged in this step.

#### [MODIFY] .agent/src/agent/core/governance.py

```
<<<SEARCH
"""
Core governance logic for the Agent CLI.

This module provides the functionality for convening the AI Governance Council,
loading agent roles from configuration, conducting preflight checks,
and executing governance audits.
"""
===
"""
TRANSITIONAL MODULE — do not import directly.

This is the original governance.py monolith, renamed to _governance_legacy.py
as part of the multi-slice decomposition defined by INFRA-101. Import via
the package facade: ``from agent.core.governance import ...``

Extracted so far:
  - load_roles → agent.core.governance.roles (INFRA-101)

Pending extraction:
  - log_governance_event, GateResult aggregation → validation.py (INFRA-101.2)
  - _parse_findings, _filter_relevant_roles, prompt helpers → panel_prompts.py (INFRA-101.3)
  - convene_council_full, convene_council_fast → panel.py (INFRA-101.4)
  - __init__.py cleanup + delete this file → INFRA-101.5
"""
>>>
```

### Step 3: Redirect `load_roles` in the legacy file to the new sub-module

After the git rename (`git mv .agent/src/agent/core/governance.py .agent/src/agent/core/_governance_legacy.py`), update the `load_roles` definition to be a re-import shim so internal callers inside the legacy file still work.

#### [MODIFY] .agent/src/agent/core/_governance_legacy.py

```
<<<SEARCH
AUDIT_LOG_FILE = config.agent_dir / "logs" / "audit_events.log"

def log_governance_event(event_type: str, details: str):
===
AUDIT_LOG_FILE = config.agent_dir / "logs" / "audit_events.log"

# NOTE: load_roles has been extracted to agent.core.governance.roles.
# This shim re-imports it to keep internal call-sites working.
from agent.core.governance.roles import load_roles  # noqa: E402


def log_governance_event(event_type: str, details: str):
>>>
```

### Step 4: Create `core/governance/roles.py` — the extracted module

#### [NEW] .agent/src/agent/core/governance/roles.py

```python
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

"""Role and persona management for the AI Governance Council.

Loads governance roles from ``agents.yaml`` and provides helpers
for resolving persona handles (``@Architect``, ``@Security``, etc.).
Falls back to a hardcoded default panel if the file is absent or malformed.
"""

import logging
from typing import Dict, List, Optional

import yaml

from agent.core.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback panel — used when agents.yaml is absent or invalid.
# ---------------------------------------------------------------------------
_DEFAULT_ROLES: List[Dict[str, str]] = [
    {
        "name": "Architect",
        "role": "architect",
        "description": "System design, ADR compliance, patterns, and dependency hygiene.",
        "focus": "System design, ADR compliance, patterns, and dependency hygiene.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Security (CISO)",
        "role": "security",
        "description": "Chief Information Security Officer. Enforcer of technical security controls, vulnerabilities, and secure coding practices.",
        "focus": "Chief Information Security Officer. Enforcer of technical security controls, vulnerabilities, and secure coding practices.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Compliance (Lawyer)",
        "role": "compliance",
        "description": "Legal & Compliance Officer. Enforcer of GDPR, SOC2, Licensing, and regulatory frameworks.",
        "focus": "Legal & Compliance Officer. Enforcer of GDPR, SOC2, Licensing, and regulatory frameworks.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "QA",
        "role": "qa",
        "description": "Test coverage, edge cases, and testability of the changes.",
        "focus": "Test coverage, edge cases, and testability of the changes.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Docs",
        "role": "docs",
        "description": "Documentation updates, clarity, and user manual accuracy.",
        "focus": "Documentation updates, clarity, and user manual accuracy.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Observability",
        "role": "observability",
        "description": "Logging, metrics, tracing, and error handling.",
        "focus": "Logging, metrics, tracing, and error handling.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Backend",
        "role": "backend",
        "description": "API design, database schemas, and backend patterns.",
        "focus": "API design, database schemas, and backend patterns.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Mobile",
        "role": "mobile",
        "description": "Mobile-specific UX, performance, and platform guidelines.",
        "focus": "Mobile-specific UX, performance, and platform guidelines.",
        "governance_checks": [],
        "instruction": "",
    },
    {
        "name": "Web",
        "role": "web",
        "description": "Web accessibility, responsive design, and browser compatibility.",
        "focus": "Web accessibility, responsive design, and browser compatibility.",
        "governance_checks": [],
        "instruction": "",
    },
]


def load_roles() -> List[Dict[str, str]]:
    """Load governance roles from ``agents.yaml``.

    Reads ``.agent/etc/agents.yaml`` and converts each ``team`` member into a
    role dict with keys ``role``, ``name``, ``description``, ``focus``,
    ``governance_checks``, and ``instruction``.

    Falls back to :data:`_DEFAULT_ROLES` if the YAML file is missing,
    empty, or otherwise unreadable.

    Returns:
        List of role dicts, one per governance panel member.
    """
    agents_file = config.etc_dir / "agents.yaml"

    if not agents_file.exists():
        logger.debug("agents.yaml not found at %s — using default roles", agents_file)
        return list(_DEFAULT_ROLES)

    try:
        with open(agents_file, "r") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning(
            "Failed to parse agents.yaml at %s: %s — using default roles",
            agents_file,
            exc,
        )
        return list(_DEFAULT_ROLES)

    team = (data or {}).get("team", [])
    if not team:
        logger.warning(
            "agents.yaml at %s has no 'team' key or empty team — using default roles",
            agents_file,
        )
        return list(_DEFAULT_ROLES)

    roles: List[Dict[str, str]] = []
    for member in team:
        name = member.get("name", "Unknown")
        desc = member.get("description", "")
        resps = member.get("responsibilities", [])

        focus = desc
        if resps:
            focus += f" Priorities: {', '.join(resps)}."

        roles.append({
            "role": member.get("role", name.lower()),
            "name": name,
            "description": desc,
            "focus": focus,
            "governance_checks": member.get("governance_checks", []),
            "instruction": member.get("instruction", ""),
        })

    return roles


def get_role(name: str, roles: Optional[List[Dict]] = None) -> Optional[Dict]:
    """Look up a role by name or handle (case-insensitive).

    Accepts both full names (``"Architect"``) and ``@``-prefixed handles
    (``"@Architect"``).

    Args:
        name: Role name or ``@Handle`` to look up.
        roles: Role list to search. Defaults to :func:`load_roles()`.

    Returns:
        Matching role dict, or ``None`` if not found.
    """
    if roles is None:
        roles = load_roles()

    normalised = name.lstrip("@").strip().lower()
    for role in roles:
        if role.get("name", "").lower() == normalised:
            return role
        if role.get("role", "").lower() == normalised:
            return role
    return None
```

### Step 5: Create test package scaffolding

> **Note**: Tests live under `.agent/tests/core/governance/` — the canonical test root for this repo, never inside `src/`.

#### [NEW] .agent/tests/core/governance/**init**.py

```python
```

#### [NEW] .agent/tests/core/governance/test_roles.py

```python
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
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent.core.governance.roles import _DEFAULT_ROLES, get_role, load_roles


# ---------------------------------------------------------------------------
# Helper: build a minimal agents.yaml in a tmp directory
# ---------------------------------------------------------------------------

def _write_agents_yaml(tmp_path: Path, content: str) -> Path:
    """Write content to agents.yaml and return the path."""
    p = tmp_path / "agents.yaml"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# load_roles — happy path
# ---------------------------------------------------------------------------

class TestLoadRolesHappyPath:
    """load_roles successfully parses a valid agents.yaml."""

    def test_returns_list_of_dicts(self, tmp_path: Path) -> None:
        """load_roles returns a list of dicts from valid YAML."""
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
        agents_file = _write_agents_yaml(tmp_path, yaml_content)

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
        """focus field includes description + responsibilities."""
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
        """role key defaults to name.lower() when not provided."""
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


# ---------------------------------------------------------------------------
# load_roles — fallback paths (AC from INFRA-101 Negative Test)
# ---------------------------------------------------------------------------

class TestLoadRolesFallback:
    """load_roles falls back gracefully to default roles."""

    def test_fallback_when_file_missing(self, tmp_path: Path) -> None:
        """Returns default roles when agents.yaml does not exist."""
        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path  # agents.yaml does not exist here
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
        """Returns default roles when agents.yaml team is empty."""
        _write_agents_yaml(tmp_path, "team: []\n")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            roles = load_roles()

        assert roles == list(_DEFAULT_ROLES)

    def test_fallback_logs_warning_on_parse_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """load_roles emits a warning when YAML is malformed (observability)."""
        import logging

        _write_agents_yaml(tmp_path, "team: [invalid: yaml: :")

        with patch("agent.core.governance.roles.config") as mock_cfg:
            mock_cfg.etc_dir = tmp_path
            with caplog.at_level(logging.WARNING, logger="agent.core.governance.roles"):
                load_roles()

        assert any("Failed to parse" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# get_role
# ---------------------------------------------------------------------------

class TestGetRole:
    """get_role resolves personas by name and @Handle."""

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
        """get_role strips @ prefix from handle."""
        result = get_role("@Architect", self._ROLES)
        assert result is not None
        assert result["role"] == "architect"

    def test_lookup_by_role_key(self) -> None:
        """get_role finds a role by its role key."""
        result = get_role("security", self._ROLES)
        assert result is not None
        assert result["name"] == "Security (CISO)"

    def test_returns_none_for_unknown(self) -> None:
        """get_role returns None for an unrecognised name."""
        result = get_role("NonExistent", self._ROLES)
        assert result is None

    def test_case_insensitive_match(self) -> None:
        """get_role is case-insensitive for name matching."""
        result = get_role("ARCHITECT", self._ROLES)
        assert result is not None


# ---------------------------------------------------------------------------
# Facade: import path compatibility (AC-4)
# ---------------------------------------------------------------------------

class TestFacadeImport:
    """Verify that load_roles is importable from the package facade."""

    def test_import_from_package(self) -> None:
        """from agent.core.governance import load_roles works without error."""
        from agent.core.governance import load_roles as _lr  # noqa: F401
        assert callable(_lr)
```

### Step 6: Create `.agent/tests/core/test_governance.py` regression suite (AC-5)

Per AC-5 all existing tests in `tests/core/test_governance.py` must pass. Since the file does not currently exist, we create it now as a regression suite for the facade interface.

#### [NEW] .agent/tests/core/test_governance.py

```python
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
        from agent.core.governance import load_roles  # noqa: F401
        assert callable(load_roles)

    def test_import_log_governance_event(self) -> None:
        from agent.core.governance import log_governance_event  # noqa: F401
        assert callable(log_governance_event)

    def test_import_convene_council_full(self) -> None:
        from agent.core.governance import convene_council_full  # noqa: F401
        assert callable(convene_council_full)

    def test_import_audit_result(self) -> None:
        from agent.core.governance import AuditResult  # noqa: F401
        assert AuditResult is not None

    def test_import_extract_references(self) -> None:
        from agent.core.governance import _extract_references  # noqa: F401
        assert callable(_extract_references)

    def test_import_validate_references(self) -> None:
        from agent.core.governance import _validate_references  # noqa: F401
        assert callable(_validate_references)

    def test_import_run_audit(self) -> None:
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
        from agent.core.governance import load_roles
        roles = load_roles()
        assert isinstance(roles, list)
        assert len(roles) > 0

    def test_each_role_has_required_keys(self) -> None:
        from agent.core.governance import load_roles
        roles = load_roles()
        for role in roles:
            assert "name" in role
            assert "focus" in role
```

## Verification Plan

### Automated Tests

- [ ] `cd .agent/src && python -m pytest agent/core/governance/tests/test_roles.py -v` — all 10 tests pass
- [ ] `cd .agent/src && python -m pytest agent/core/tests/test_governance.py -v` — all tests pass
- [ ] `cd .agent/src && python -c "import agent.cli"` — no ImportError or circular import (AC-6)
- [ ] `cd .agent/src && python -c "from agent.core.governance import load_roles, convene_council_full, AuditResult, _extract_references"` — all symbols available (AC-4)

### Manual Verification

- [ ] Run `agent check --story INFRA-101` to exercise the governance pipeline end-to-end after the package is in place.
- [ ] Confirm `agent preflight --story INFRA-101` reaches the AI Governance Council step without import errors.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md entry added under `## [Unreleased]` — `refactor: extract governance roles module (INFRA-101)`
- [ ] `.agent/cache/plans/INFRA/INFRA-101-plan.md` already exists (auto-generated by CLI)

### Observability

- [ ] `load_roles` emits `logger.warning(...)` (not silent `pass`) on YAML parse failure
- [ ] No PII in log messages

### Testing

- [ ] All tests in `agent/core/governance/tests/test_roles.py` pass
- [ ] All tests in `agent/core/tests/test_governance.py` pass
- [ ] `python -c "import agent.cli"` succeeds

## Copyright

Copyright 2026 Justin Cook
