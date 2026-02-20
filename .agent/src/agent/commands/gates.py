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

from agent.core.logger import get_logger

logger = get_logger(__name__)


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


def run_qa_gate(test_command: str = "make test") -> GateResult:
    """Execute the configured test command as a QA gate.

    Args:
        test_command: Shell command to run tests (default: ``make test``).

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


def log_skip_audit(gate_name: str) -> None:
    """Log a timestamped audit entry when a governance gate is skipped.

    Args:
        gate_name: Human-readable name of the skipped gate.
    """
    timestamp = datetime.now().isoformat()
    logger.warning("[AUDIT] %s skipped at %s", gate_name, timestamp)
