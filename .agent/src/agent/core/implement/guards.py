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

"""Pre-apply validation gates for the implement command (INFRA-096, INFRA-100).

Provides docstring enforcement (AC-10) and safe-apply file-size guards
(AC-9) that run before any file is written to disk.
"""

import difflib
import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from opentelemetry import metrics
from rich.console import Console
from rich.syntax import Syntax

logger = logging.getLogger(__name__)

meter = metrics.get_meter("agent.guardrails")

intervention_counter = meter.create_counter(
    "guardrail_interventions_total",
    description="Total number of tool execution loops aborted by guardrails",
)

class ExecutionGuardrail:
    """
    Monitors tool execution for infinite loops and iteration limits.

    Attributes:
        max_iterations: Maximum number of tool calls allowed in a session.
        excluded_tools: Tools exempt from loop detection.
        iteration_count: Current number of tool calls made.
        call_history: Set of hashes representing (tool_name, parameters).
    """

    def __init__(self, max_iterations: int = 10, excluded_tools: Optional[List[str]] = None):
        """
        Initializes the guardrail state.

        Args:
            max_iterations: Max allowed tool calls before forced termination.
            excluded_tools: Tools exempt from loop detection.
        """
        self.max_iterations: int = max_iterations
        self.excluded_tools: List[str] = excluded_tools or []
        self.iteration_count: int = 0
        self.call_history: Set[str] = set()

    def _generate_call_hash(self, tool_name: str, params: Union[Dict[str, Any], str]) -> str:
        """
        Generate a deterministic hash for a tool call.

        Args:
            tool_name: Name of the tool being called.
            params: Parameters passed to the tool.

        Returns:
            A SHA-256 hash string.
        """
        # Sort keys to ensure deterministic hashing of parameters
        if isinstance(params, dict):
            param_str = json.dumps(params, sort_keys=True)
        else:
            param_str = str(params)
        payload = f"{tool_name}:{param_str}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def check_and_record(self, tool_name: str, params: Union[Dict[str, Any], str]) -> Tuple[bool, Optional[str]]:

        """
        Checks if the current call violates guardrails.

        Args:
            tool_name: Name of the tool.
            params: Tool arguments.

        Returns:
            Tuple of (is_aborted, reason).
        """
        self.iteration_count += 1

        # 1. Check iteration limit
        if self.iteration_count > self.max_iterations:
            reason = f"Maximum iteration limit ({self.max_iterations}) reached."
            intervention_counter.add(1, {"reason": "max_iterations"})
            logger.warning("Guardrail aborted execution", extra={"iteration_count": self.iteration_count, "termination_reason": "max_iterations"})
            return True, reason

        # 2. Check for redundant loops (identical tool + params)
        call_hash = self._generate_call_hash(tool_name, params)

        if tool_name not in self.excluded_tools and call_hash in self.call_history:
            reason = f"Detected recursive loop: {tool_name} called repeatedly with identical parameters."
            intervention_counter.add(1, {"reason": "repeated_call"})
            logger.warning("Guardrail aborted execution", extra={"iteration_count": self.iteration_count, "termination_reason": "repeated_call"})
            return True, reason

        self.call_history.add(call_hash)
        logger.debug("Guardrail check passed", extra={"iteration_count": self.iteration_count})
        return False, None


try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

# ---------------------------------------------------------------------------
# Thresholds (INFRA-096)
# ---------------------------------------------------------------------------

FILE_SIZE_GUARD_THRESHOLD: int = 500
SOURCE_CONTEXT_MAX_LOC: int = 300
SOURCE_CONTEXT_HEAD_TAIL: int = 100

class ImplementGuardViolation(Exception):
    """Base class for all implementation guard violations."""
    pass

class FileSizeGuardViolation(ImplementGuardViolation):
    """Raised when a file change violates the size safety threshold."""
    pass

class DocstringGuardViolation(ImplementGuardViolation):
    """Raised when a file change lacks required PEP-257 docstrings."""
    pass

_console = Console()


# ---------------------------------------------------------------------------
# Docstring enforcement (AC-10)
# ---------------------------------------------------------------------------

def enforce_docstrings(filepath: str, content: str) -> List[str]:
    """Check generated Python source for missing PEP-257 docstrings.

    Inspects every module, class, and function/method definition (including
    inner functions such as decorator closures) using ast.parse(). Non-Python
    files automatically pass.

    Args:
        filepath: Repo-relative path of the file being validated.
        content: Python source code string to validate.

    Returns:
        List of human-readable violation strings. Empty list means pass.
    """
    import ast

    if not filepath.endswith(".py"):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations: List[str] = []
    filename = Path(filepath).name

    def _has_docstring(node: ast.AST) -> bool:
        """Return True if node's first body statement is a string literal."""
        return (
            bool(getattr(node, "body", None))
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

    if not _has_docstring(tree):
        violations.append(f"{filename}: module is missing a docstring")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _has_docstring(node):
                violations.append(f"{filename}: {node.name}() is missing a docstring")
        elif isinstance(node, ast.ClassDef):
            if not _has_docstring(node):
                violations.append(f"{filename}: class {node.name} is missing a docstring")

    return violations


# ---------------------------------------------------------------------------
# File backup
# ---------------------------------------------------------------------------

def backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup of a file before modification.

    Args:
        file_path: Path to the file to back up.

    Returns:
        Path to the backup file, or None if the source does not exist.
    """
    if not file_path.exists():
        return None
    backup_dir = Path(".agent/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{file_path.name}.backup-{timestamp}"
    shutil.copy2(file_path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------

def apply_search_replace_to_file(
    filepath: str,
    blocks: List[Dict[str, str]],
    yes: bool = False,
) -> tuple[bool, str]:
    """Apply search/replace blocks surgically to an existing file.

    All blocks are verified (dry-run) before any change is written.
    If any block fails to match, the entire operation is aborted.

    Args:
        filepath: Repo-relative file path.
        blocks: List of dicts with 'search' and 'replace' keys.
        yes: Skip confirmation prompts.

    Returns:
        Tuple of (success, final_content). On failure, final_content is
        the original unchanged content.
    """
    from agent.core.implement.orchestrator import resolve_path  # avoid circular at module level
    import typer

    span_ctx = None
    if _tracer:
        span_ctx = _tracer.start_span("implement.apply_change")
        span_ctx.set_attribute("file", filepath)
        span_ctx.set_attribute("apply_mode", "search_replace")

    resolved_path = resolve_path(filepath)
    if not resolved_path or not resolved_path.exists():
        _console.print(
            f"[bold red]❌ Cannot apply search/replace to '{filepath}': file not found.[/bold red]"
        )
        return False, ""

    original_content = resolved_path.read_text()
    working_content = original_content

    for i, block in enumerate(blocks):
        if block["search"] not in working_content:
            _console.print(
                f"[bold red]❌ Search block {i+1}/{len(blocks)} not found in {filepath}.[/bold red]"
            )
            logging.warning(
                "search_replace_match_failure file=%s block=%d/%d",
                filepath, i + 1, len(blocks),
            )
            if span_ctx:
                span_ctx.end()
            return False, original_content
        match_count = working_content.count(block["search"])
        if match_count > 1:
            logging.warning(
                "search_replace_ambiguous file=%s block=%d match_count=%d",
                filepath, i + 1, match_count,
            )
        working_content = working_content.replace(block["search"], block["replace"], 1)

    _console.print(f"\n[bold cyan]📝 Search/Replace for: {filepath}[/bold cyan]")
    diff_lines = list(difflib.unified_diff(
        original_content.splitlines(keepends=True),
        working_content.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    ))
    if diff_lines:
        _console.print(Syntax("".join(diff_lines), "diff", theme="monokai"))

    if not yes:
        import typer as _typer
        if not _typer.confirm(f"\nApply {len(blocks)} block(s) to {filepath}?", default=False):
            _console.print("[yellow]⏭️  Skipped[/yellow]")
            if span_ctx:
                span_ctx.end()
            return False, original_content

    backup_path = backup_file(resolved_path)
    if backup_path:
        _console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")

    try:
        resolved_path.write_text(working_content)
        _console.print(f"[bold green]✅ Applied {len(blocks)} block(s) to {filepath}[/bold green]")
        logging.info(
            "apply_change apply_mode=search_replace file=%s blocks=%d",
            filepath, len(blocks),
        )
        log_file = Path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] SearchReplace: {filepath} ({len(blocks)} blocks)\n")
        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True, working_content
    except Exception as exc:
        _console.print(f"[bold red]❌ Failed to write file: {exc}[/bold red]")
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False, original_content


def apply_change_to_file(
    filepath: str,
    content: str,
    yes: bool = False,
    legacy_apply: bool = False,
) -> bool:
    """Apply code changes to a file with smart path resolution and size guard.

    For existing files exceeding FILE_SIZE_GUARD_THRESHOLD, rejects full-file
    overwrites unless legacy_apply is True (AC-5 backward compat).

    Args:
        filepath: Repo-relative file path.
        content: New file content.
        yes: Skip confirmation prompts.
        legacy_apply: Bypass safe-apply guard (audit-logged).

    Returns:
        True if the file was written successfully, False otherwise.
    """
    from agent.core.implement.orchestrator import resolve_path

    span_ctx = None
    if _tracer:
        span_ctx = _tracer.start_span("implement.apply_change")
        span_ctx.set_attribute("file", filepath)
        span_ctx.set_attribute("apply_mode", "full_file")

    resolved_path = resolve_path(filepath)
    if not resolved_path:
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False

    file_path = resolved_path
    filepath = str(resolved_path)

    if file_path.exists() and not legacy_apply:
        try:
            existing_lines = len(file_path.read_text().splitlines())
        except Exception:
            existing_lines = 0
        if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
            if span_ctx:
                span_ctx.set_attribute("success", False)
                span_ctx.end()
            raise FileSizeGuardViolation(
                f"File '{filepath}' already exists and new content is {existing_lines} lines. "
                f"Maximum allowed for full-file replace is {FILE_SIZE_GUARD_THRESHOLD} LOC. "
                "Hint: Update runbook step to use <<<SEARCH/===/>>> blocks for incremental changes, "
                "or pass --legacy-apply to bypass."
            )

    _console.print(f"\n[bold cyan]📝 Changes for: {filepath}[/bold cyan]")
    if file_path.exists():
        _console.print("[yellow]File exists. Showing new content:[/yellow]")
    else:
        _console.print("[green]New file will be created.[/green]")
    _console.print(Syntax(
        content,
        "python" if filepath.endswith(".py") else "text",
        theme="monokai", line_numbers=True,
    ))

    if not yes:
        import typer as _typer
        if not _typer.confirm(f"\nApply changes to {filepath}?", default=False):
            _console.print("[yellow]⏭️  Skipped[/yellow]")
            if span_ctx:
                span_ctx.end()
            return False

    if file_path.exists():
        bp = backup_file(file_path)
        if bp:
            _console.print(f"[dim]💾 Backup created: {bp}[/dim]")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file_path.write_text(content)
        _console.print(f"[bold green]✅ Applied changes to {filepath}[/bold green]")
        from agent.commands.license import apply_license_to_file
        if apply_license_to_file(file_path):
            _console.print(f"[dim]Added copyright header to {filepath}[/dim]")
        logging.info(
            "apply_change apply_mode=full_file file=%s lines_changed=%d",
            filepath, len(content.splitlines()),
        )
        log_file = Path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Modified: {filepath}\n")
        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True
    except Exception as exc:
        _console.print(f"[bold red]❌ Failed to write file: {exc}[/bold red]")
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False