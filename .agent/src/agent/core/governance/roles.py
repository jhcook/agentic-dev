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

Story: INFRA-101
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
        "description": (
            "Chief Information Security Officer. Enforcer of technical security controls, "
            "vulnerabilities, and secure coding practices."
        ),
        "focus": (
            "Chief Information Security Officer. Enforcer of technical security controls, "
            "vulnerabilities, and secure coding practices."
        ),
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
    empty, or otherwise unreadable. Emits a structured ``WARNING`` log entry
    on parse failure for observability (replaces the silent ``except: pass``
    from the original monolith).

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
    """Look up a role by name or ``@``-prefixed handle (case-insensitive).

    Accepts both full names (e.g. ``"Architect"``) and ``@``-prefixed handles
    (e.g. ``"@Architect"``). Matches on both the ``name`` and ``role`` keys.

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
