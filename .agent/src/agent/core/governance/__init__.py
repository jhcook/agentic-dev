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

Decomposition status (INFRA-101 series):
  - roles.py      ✅ Extracted (INFRA-101)
  - validation.py ⏳ Pending (INFRA-101.2)
  - panel.py      ⏳ Pending (INFRA-101.4)
"""

# ── Roles sub-module (INFRA-101) ──────────────────────────────────────────
from agent.core.governance.roles import (  # noqa: F401
    load_roles,
    get_role,
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
    # Roles (extracted)
    "load_roles",
    "get_role",
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
