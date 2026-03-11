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

"""Code quality checks: journey coverage, LOC enforcement, import hygiene.

This module contains check logic that is concerned with *code quality* —
whether the committed codebase meets the journey-test-coverage contract and
other structural quality policies — distinct from system health checks
(see system.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from agent.core.config import config
from agent.core.logger import get_logger

logger = get_logger(__name__)


class JourneyCoverageResult(TypedDict):
    """Structured return value from :func:`check_journey_coverage`."""

    passed: bool
    total: int
    linked: int
    missing: int
    warnings: List[str]
    missing_ids: List[str]


import time
from agent.commands.gates import GateResult
import subprocess

def check_code_quality() -> GateResult:
    """Run LOC and Import checks.
    
    Returns:
        A GateResult indicating pass/fail status of quality checks.
    """
    start = time.time()
    
    from agent.core.config import config
    root_dir = config.repo_root
    scripts_dir = root_dir / "scripts"
    
    loc_res = subprocess.run(["python3", str(scripts_dir / "check_loc.py")], capture_output=True, text=True, cwd=root_dir)
    import_res = subprocess.run(["python3", str(scripts_dir / "check_imports.py")], capture_output=True, text=True, cwd=root_dir)
    
    success = loc_res.returncode == 0 and import_res.returncode == 0
    message = (loc_res.stdout + import_res.stdout).strip() or "All quality checks passed."
    
    elapsed = time.time() - start
    return GateResult(
        name="Code Quality",
        passed=success,
        elapsed_seconds=elapsed,
        details=message
    )


def check_journey_coverage(
    repo_root: Optional[Path] = None,
) -> JourneyCoverageResult:
    """Check journey → test coverage for COMMITTED/ACCEPTED journeys.

    Iterates over every journeys YAML file in ``<repo_root>/.agent/cache/journeys/``
    and verifies that each ``COMMITTED`` or ``ACCEPTED`` journey has at least one
    test file linked under ``implementation.tests``, and that the linked file
    exists on disk.

    Args:
        repo_root: Optional override for the repository root directory.
            Defaults to :attr:`agent.core.config.config.repo_root`.

    Returns:
        :class:`JourneyCoverageResult` with keys:

        - ``passed`` (bool): *True* when every committed journey has tests.
        - ``total`` (int): Number of committed/accepted journeys examined.
        - ``linked`` (int): Number with valid test links.
        - ``missing`` (int): Number missing tests.
        - ``warnings`` (list[str]): Human-readable warning messages.
        - ``missing_ids`` (list[str]): Journey IDs with missing tests.
    """
    import yaml  # ADR-025: local import

    root = repo_root or config.repo_root
    journeys_dir = root / ".agent" / "cache" / "journeys"
    result: JourneyCoverageResult = {
        "passed": True,
        "total": 0,
        "linked": 0,
        "missing": 0,
        "warnings": [],
        "missing_ids": [],
    }

    if not journeys_dir.exists():
        logger.debug("Journeys directory absent — coverage check trivially passes")
        return result

    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            state = (data.get("state") or "DRAFT").upper()
            if state not in ("COMMITTED", "ACCEPTED"):
                continue

            result["total"] += 1
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)

            if not tests:
                result["missing"] += 1
                result["missing_ids"].append(jid)
                result["warnings"].append(f"{jid}: No tests linked")
                result["passed"] = False
                continue

            all_exist = True
            for t in tests:
                tp = Path(t)
                if tp.is_absolute():
                    result["warnings"].append(f"{jid}: Absolute test path '{t}'")
                    all_exist = False
                    continue
                if not (root / tp).exists():
                    result["warnings"].append(f"{jid}: Test file not found: '{t}'")
                    all_exist = False

            if all_exist:
                result["linked"] += 1
            else:
                result["missing"] += 1
                result["missing_ids"].append(jid)
                result["passed"] = False

    logger.debug(
        "Journey coverage check complete",
        extra={
            "total": result["total"],
            "linked": result["linked"],
            "missing": result["missing"],
            "passed": result["passed"],
        },
    )
    return result