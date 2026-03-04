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

"""Post-apply governance gates for the implement command.

Provides composable gate functions (security scan, QA validation,
documentation check) that run after AI-generated code is applied.
Each gate returns a GateResult with pass/fail status and timing.
"""

import ast
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from opentelemetry import trace

from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class GateResult:
    """Result of a single governance gate execution."""

    name: str
    passed: bool
    elapsed_seconds: float
    details: str = ""


def run_security_scan(
    filepaths: List[Path],
    patterns_path: Path,
) -> GateResult:
    """Scan files for security vulnerabilities using externalized patterns.

    Reads regex patterns from a YAML file and checks each file against them.
    Reports presence of matches without logging matched content (PII-safe).

    Args:
        filepaths: List of file paths to scan.
        patterns_path: Path to the security_patterns.yaml file.

    Returns:
        GateResult with pass/fail status and details.
    """
    start = time.time()

    if not patterns_path.exists():
        elapsed = time.time() - start
        logger.warning("Security patterns file not found: %s", patterns_path)
        return GateResult(
            name="Security Scan",
            passed=True,
            elapsed_seconds=elapsed,
            details="Skipped — no security_patterns.yaml found.",
        )

    try:
        import yaml  # ADR-025: lazy import
        patterns: dict = yaml.safe_load(patterns_path.read_text()) or {}
    except Exception as exc:  # catch yaml.YAMLError + ImportError
        elapsed = time.time() - start
        logger.error("Error parsing security patterns: %s", exc)
        return GateResult(
            name="Security Scan",
            passed=False,
            elapsed_seconds=elapsed,
            details=f"Invalid YAML in {patterns_path.name}: {exc}",
        )

    findings: List[str] = []
    for filepath in filepaths:
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(errors="ignore")
        except OSError:
            continue

        for pattern_name, pattern_regex in patterns.items():
            if re.search(pattern_regex, content):
                findings.append(f"{pattern_name} in {filepath.name}")
                logger.warning(
                    "Security finding: %s detected in %s",
                    pattern_name,
                    filepath.name,
                )

    elapsed = time.time() - start
    if findings:
        return GateResult(
            name="Security Scan",
            passed=False,
            elapsed_seconds=elapsed,
            details="; ".join(findings),
        )
    return GateResult(
        name="Security Scan",
        passed=True,
        elapsed_seconds=elapsed,
        details=f"Scanned {len(filepaths)} file(s) — clean.",
    )


def run_qa_gate(test_command: str = "pytest .agent/tests") -> GateResult:
    """Execute the configured test command as a QA gate.

    Args:
        test_command: Shell command to run tests (default: ``pytest .agent/tests``).

    Returns:
        GateResult with pass/fail based on exit code.
    """
    start = time.time()
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        elapsed = time.time() - start
        if result.returncode != 0:
            # Show last 10 lines of stderr for context
            stderr_tail = "\n".join(result.stderr.strip().splitlines()[-10:])
            return GateResult(
                name="QA Validation",
                passed=False,
                elapsed_seconds=elapsed,
                details=f"Exit code {result.returncode}.\n{stderr_tail}",
            )
        return GateResult(
            name="QA Validation",
            passed=True,
            elapsed_seconds=elapsed,
            details="All tests passed.",
        )
    except FileNotFoundError:
        elapsed = time.time() - start
        return GateResult(
            name="QA Validation",
            passed=False,
            elapsed_seconds=elapsed,
            details=f"Command not found: {test_command}",
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return GateResult(
            name="QA Validation",
            passed=False,
            elapsed_seconds=elapsed,
            details="Test command timed out after 300s.",
        )


def run_docs_check(filepaths: List[Path]) -> GateResult:
    """Verify that new/modified Python files have docstrings on public functions.

    Uses AST parsing — only checks top-level and class-level function definitions
    whose names do not start with ``_``.

    Args:
        filepaths: List of Python file paths to check.

    Returns:
        GateResult with pass/fail and list of undocumented functions.
    """
    start = time.time()
    missing: List[str] = []

    py_files = [f for f in filepaths if f.suffix == ".py" and f.exists()]
    if not py_files:
        elapsed = time.time() - start
        return GateResult(
            name="Documentation Check",
            passed=True,
            elapsed_seconds=elapsed,
            details="No Python files to check.",
        )

    for filepath in py_files:
        try:
            source = filepath.read_text(errors="ignore")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, OSError) as exc:
            logger.warning("Could not parse %s: %s", filepath.name, exc)
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only check public functions (not _private)
                if node.name.startswith("_"):
                    continue
                if ast.get_docstring(node) is None:
                    missing.append(f"{filepath.name}:{node.name}()")

    elapsed = time.time() - start
    if missing:
        return GateResult(
            name="Documentation Check",
            passed=False,
            elapsed_seconds=elapsed,
            details=f"Missing docstrings: {', '.join(missing[:10])}",
        )
    return GateResult(
        name="Documentation Check",
        passed=True,
        elapsed_seconds=elapsed,
        details=f"Checked {len(py_files)} file(s) — all documented.",
    )


def log_skip_audit(gate_name: str, resource_id: str = "") -> None:
    """Log a timestamped audit entry when a governance gate is skipped.

    Args:
        gate_name: Human-readable name of the skipped gate.
        resource_id: Identifier for the resource being bypassed (e.g. story ID).
    """
    import getpass

    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "user": getpass.getuser(),
        "gate": gate_name,
        "resource": resource_id,
        "action": "BYPASS",
    }
    logger.warning("[AUDIT] gate_bypass %s", audit_entry)


# ── Commit Atomicity Gates (INFRA-091) ────────────────────────

CONVENTIONAL_PREFIXES = {
    "feat", "fix", "refactor", "chore", "docs",
    "test", "ci", "style", "perf", "build",
}


def check_commit_size(max_per_file: int = 20, max_total: int = 100) -> GateResult:
    """Check staged changes against per-file and total line count thresholds.

    Warns if any single file has more than max_per_file lines changed,
    or if the total across all files exceeds max_total.

    Args:
        max_per_file: Maximum lines changed per file before warning.
        max_total: Maximum total lines changed before warning.

    Returns:
        GateResult with pass/fail and details of any threshold violations.
    """
    with tracer.start_as_current_span("gate.commit_size") as span:
        return _check_commit_size_impl(span, max_per_file, max_total)


def _check_commit_size_impl(span: trace.Span, max_per_file: int, max_total: int) -> GateResult:
    start = time.time()
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            elapsed = time.time() - start
            return GateResult(
                name="Commit Size",
                passed=True,
                elapsed_seconds=elapsed,
                details="Skipped — git diff failed.",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        elapsed = time.time() - start
        return GateResult(
            name="Commit Size", passed=True,
            elapsed_seconds=elapsed, details="Skipped — git not available.",
        )

    violations: List[str] = []
    total_changed = 0
    max_file_changed = 0

    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        # Binary files show '-' for additions/deletions
        try:
            additions = int(parts[0])
            deletions = int(parts[1])
        except ValueError:
            continue
        filename = parts[2]
        file_changed = additions + deletions
        total_changed += file_changed
        max_file_changed = max(max_file_changed, file_changed)

        if file_changed > max_per_file:
            violations.append(f"{filename}: {file_changed} lines (limit {max_per_file})")

    if total_changed > max_total:
        violations.append(f"Total: {total_changed} lines (limit {max_total})")

    elapsed = time.time() - start
    logger.info(
        "gate=commit_size max_file_count=%d total=%d passed=%s",
        max_file_changed, total_changed, not bool(violations),
    )
    span.set_attribute("gate.passed", not bool(violations))
    span.set_attribute("gate.total_changed", total_changed)
    if violations:
        return GateResult(
            name="Commit Size", passed=False,
            elapsed_seconds=elapsed, details="; ".join(violations),
        )
    return GateResult(
        name="Commit Size", passed=True,
        elapsed_seconds=elapsed,
        details=f"Total: {total_changed} lines — within limits.",
    )


def check_commit_message(message: str) -> GateResult:
    """Validate commit message for conventional format and single-purpose.

    Checks:
    1. Message starts with a valid conventional commit prefix.
    2. Message body does not contain ' and ' joining distinct actions.

    Args:
        message: The full commit message string.

    Returns:
        GateResult with pass/fail and details.
    """
    with tracer.start_as_current_span("gate.commit_message") as span:
        return _check_commit_message_impl(span, message)


def _check_commit_message_impl(span: trace.Span, message: str) -> GateResult:
    start = time.time()
    if not message.strip():
        elapsed = time.time() - start
        return GateResult(
            name="Commit Message", passed=False,
            elapsed_seconds=elapsed, details="Empty commit message.",
        )

    violations: List[str] = []
    first_line = message.strip().splitlines()[0]

    # 1. Conventional commit prefix
    prefix_match = re.match(r"^(\w+)(?:\([^)]*\))?:", first_line)
    if not prefix_match or prefix_match.group(1) not in CONVENTIONAL_PREFIXES:
        violations.append(
            f"Missing conventional prefix. Expected one of: "
            f"{', '.join(sorted(CONVENTIONAL_PREFIXES))}"
        )

    # 2. "And" test — check subject line only (body text is exempt)
    colon_idx = first_line.find(":")
    body = first_line[colon_idx + 1:] if colon_idx != -1 else first_line
    if " and " in body.lower():
        violations.append('Compound message — contains " and " (split into separate commits)')

    elapsed = time.time() - start
    logger.info(
        "gate=commit_message passed=%s violations=%d",
        not bool(violations), len(violations),
    )
    span.set_attribute("gate.passed", not bool(violations))
    if violations:
        return GateResult(
            name="Commit Message", passed=False,
            elapsed_seconds=elapsed, details="; ".join(violations),
        )
    return GateResult(
        name="Commit Message", passed=True,
        elapsed_seconds=elapsed, details="Valid conventional commit.",
    )


def check_domain_isolation(filepaths: List[Path]) -> GateResult:
    """Verify that a changeset does not mix core/ and addons/ domains.

    Args:
        filepaths: List of file paths in the changeset.

    Returns:
        GateResult — FAIL if both core/ and addons/ are touched.
    """
    with tracer.start_as_current_span("gate.domain_isolation") as span:
        return _check_domain_isolation_impl(span, filepaths)


def _check_domain_isolation_impl(span: trace.Span, filepaths: List[Path]) -> GateResult:
    start = time.time()
    has_core = any("core" in p.parts for p in filepaths)
    has_addons = any("addons" in p.parts for p in filepaths)

    elapsed = time.time() - start
    passed = not (has_core and has_addons)
    logger.info(
        "gate=domain_isolation has_core=%s has_addons=%s passed=%s",
        has_core, has_addons, passed,
    )
    span.set_attribute("gate.passed", passed)
    if has_core and has_addons:
        return GateResult(
            name="Domain Isolation", passed=False,
            elapsed_seconds=elapsed,
            details="Changeset touches both core/ and addons/ — split into separate commits.",
        )
    return GateResult(
        name="Domain Isolation", passed=True,
        elapsed_seconds=elapsed,
        details="Single domain.",
    )


# ── PR Size Gate (INFRA-092) ─────────────────────────────────

def check_pr_size(threshold: int = 400, commit_message: Optional[str] = None) -> GateResult:
    """Enforce a line-of-code limit on staged changes.

    Serves as a circuit breaker to prevent context stuffing in AI governance.
    Exempts:
    - Net-negative changes (more deletions than additions)
    - Automated chores/refactors via commit message prefix
    - Non-code assets (images, locks, configs)

    Args:
        threshold: Maximum allowed lines of code additions.
        commit_message: Commit message to check for bypass prefixes.

    Returns:
        GateResult with pass/fail and details.
    """
    with tracer.start_as_current_span("gate.pr_size") as span:
        return _check_pr_size_impl(span, threshold, commit_message)


def _check_pr_size_impl(span: trace.Span, threshold: int, commit_message: Optional[str]) -> GateResult:
    start = time.time()

    # Bypass by prefix
    if commit_message and (
        commit_message.startswith("chore(deps):")
        or commit_message.startswith("refactor(auto):")
    ):
        elapsed = time.time() - start
        span.set_attribute("gate.passed", True)
        span.set_attribute("gate.bypass", "prefix")
        return GateResult(
            name="PR Size", passed=True,
            elapsed_seconds=elapsed,
            details=f"Bypassed via commit prefix: {commit_message.split(':')[0]}",
        )

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            elapsed = time.time() - start
            return GateResult(
                name="PR Size", passed=True,
                elapsed_seconds=elapsed,
                details="Skipped — git diff failed.",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        elapsed = time.time() - start
        return GateResult(
            name="PR Size", passed=True,
            elapsed_seconds=elapsed,
            details="Skipped — git not available.",
        )

    total_additions = 0
    total_deletions = 0
    excluded_ext = {
        '.json', '.yaml', '.yml', '.png', '.jpg', '.jpeg', '.svg', '.lock',
        '.md', '.txt', '.ttf', '.otf', '.mp4', '.mov', '.snap', '.csv', '.gif',
    }

    for line in result.stdout.strip().splitlines():
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        adds, dels, path = parts[0], parts[1], parts[2]
        if adds == '-' or dels == '-':
            continue
        if any(path.endswith(ext) for ext in excluded_ext):
            continue
        try:
            total_additions += int(adds)
            total_deletions += int(dels)
        except ValueError:
            continue

    span.set_attribute("gate.total_additions", total_additions)
    span.set_attribute("gate.total_deletions", total_deletions)
    span.set_attribute("gate.threshold", threshold)

    elapsed = time.time() - start

    if total_deletions > total_additions:
        decision = "pass_net_negative"
        span.set_attribute("gate.passed", True)
        span.set_attribute("gate.bypass", "net_negative")
        result = GateResult(
            name="PR Size", passed=True,
            elapsed_seconds=elapsed,
            details=f"Net-negative change (+{total_additions}/-{total_deletions})",
        )
    elif total_additions > threshold:
        decision = "fail"
        span.set_attribute("gate.passed", False)
        result = GateResult(
            name="PR Size", passed=False,
            elapsed_seconds=elapsed,
            details=(
                f"PR size exceeds {threshold} lines (Found: {total_additions}). "
                "Split the PR or use 'refactor(auto):' prefix."
            ),
        )
    else:
        decision = "pass"
        span.set_attribute("gate.passed", True)
        result = GateResult(
            name="PR Size", passed=True,
            elapsed_seconds=elapsed,
            details=f"PR size OK: {total_additions} additions (limit {threshold})",
        )

    logger.info(
        "gate=pr_size total_additions=%d total_deletions=%d threshold=%d decision=%s",
        total_additions, total_deletions, threshold, decision,
    )
    return result
