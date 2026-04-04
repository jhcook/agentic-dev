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

"""File application and linting utilities for the implement pipeline.

Split from guards.py (INFRA-145) to satisfy the 1000-LOC governance hard limit.
All public symbols are re-exported from guards.py for backward compatibility.
"""

import ast
import difflib
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rich.console import Console
from rich.syntax import Syntax

from agent.utils.path_utils import validate_path_integrity
from agent.utils.validation_formatter import format_projected_syntax_error

logger = logging.getLogger(__name__)
_console = Console()

# ---------------------------------------------------------------------------
# Lazy tracer — mirrors guards.py pattern to avoid circular imports
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace as _otel_trace

    _tracer = _otel_trace.get_tracer(__name__)
except Exception:  # pragma: no cover

    class _NoOpTracer:  # type: ignore[no-untyped-def]
        def start_span(self, *a, **kw):
            return None

        def start_as_current_span(self, *a, **kw):
            from contextlib import nullcontext

            return nullcontext()

    _tracer: Any = _NoOpTracer()


FILE_SIZE_GUARD_THRESHOLD: int = 500  # lines — mirrors guards.py constant


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
    from agent.core.config import resolve_repo_path

    backup_dir = resolve_repo_path(".agent/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{file_path.name}.backup-{timestamp}"
    shutil.copy2(file_path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Search/Replace application
# ---------------------------------------------------------------------------

from agent.core.implement.sr_validation import (  # noqa: E402
    fuzzy_find_and_replace as _fuzzy_find_and_replace,
)


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
    from agent.core.config import resolve_repo_path

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
        if block["search"] in working_content:
            match_count = working_content.count(block["search"])
            if match_count > 1:
                logging.warning(
                    "search_replace_ambiguous file=%s block=%d match_count=%d",
                    filepath, i + 1, match_count,
                )
            working_content = working_content.replace(block["search"], block["replace"], 1)
        else:
            # Idempotency: check if REPLACE text already exists (already applied)
            if block["replace"] and block["replace"] in working_content:
                logging.info(
                    "search_replace_already_applied file=%s block=%d/%d",
                    filepath, i + 1, len(blocks),
                )
                _console.print(
                    f"[dim]⏭️  Block {i+1}/{len(blocks)} already applied to {filepath}[/dim]"
                )
                continue

            # Fuzzy match fallback: find best matching region
            _fuzzy_result = _fuzzy_find_and_replace(
                working_content, block["search"], block["replace"], filepath, i + 1, len(blocks)
            )
            if _fuzzy_result is not None:
                working_content = _fuzzy_result
            else:
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
        log_file = resolve_repo_path(".agent/logs/implement_changes.log")
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


# ---------------------------------------------------------------------------
# Projected syntax validation
# ---------------------------------------------------------------------------


def check_projected_syntax(
    filepath: Path, search: str, replace: str, root_dir: Optional[Path] = None
) -> Optional[str]:
    """Validate Python syntax after projecting a [MODIFY] S/R block in-memory.

    Covers AC-1 to AC-6. AC-7 (NameError detection) is deferred to INFRA-178.
    Pass ``root_dir`` (the repo root) to enable path-traversal prevention (AC-6).
    Only runs for .py files; all projection is done in-memory (no disk side effects).
    """
    if filepath.suffix != ".py":
        return None

    _root = root_dir if root_dir is not None else filepath.parent
    if not validate_path_integrity(str(filepath), _root):
        return f"Gate 3.5: '{filepath.name}' resolves outside the project root — skipped."

    try:
        if not filepath.exists():
            return None

        content = filepath.read_text(encoding="utf-8")

        # AC-5: search absent → S/R gate owns that check; this gate is a no-op.
        if search not in content:
            return None

        projected_content = content.replace(search, replace, 1)
        ast.parse(projected_content)
        return None

    except SyntaxError as e:
        logger.warning(
            "projected_syntax_gate_fail",
            extra={"file": filepath.name, "error": str(e.msg), "line": e.lineno},
        )
        return format_projected_syntax_error(filepath, str(e.msg), e.lineno)
    except Exception as exc:
        return f"Warning: Could not project syntax for {filepath.name}: {exc}"


# check_api_surface_renames and _extract_public_symbols live in rename_guard.py (INFRA-179)


def check_test_imports_resolvable(
    file_path: "Union[str, Path]", content: str, session_symbols: Set[str]
) -> Optional[str]:
    """Verify that all imports in a [NEW] test file are resolvable.

    Validates imports against symbols defined within the current runbook session
    or resolvable via the environment (stdlib and installed packages).
    Ignores imports inside TYPE_CHECKING blocks to avoid false positives.

    Args:
        file_path: Repo-relative path of the file being checked (str or Path).
        content: The Python source code of the block.
        session_symbols: Fully-qualified or basename symbols defined in the runbook.

    Returns:
        A correction prompt naming unresolved symbols, or None if validation passes.
    """
    import importlib.util
    from pathlib import Path as _Path

    # Normalise to str so both str and Path callers work correctly
    file_path = str(file_path)
    _p = _Path(file_path)
    # 1. Exit early if naming pattern does not match tests (AC-5)
    is_test = (
        "tests/" in file_path.replace("\\", "/")
        or _p.name.startswith("test_")
        or _p.name.endswith("_test.py")
    )
    if not is_test:
        return None

    # 2. Parse content using ast.parse
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Syntax issues are handled by Gate 3.5; this gate becomes a no-op.
        return None

    unresolved = set()

    # 3. Walk the AST to find Import and ImportFrom nodes
    class ResolutionVisitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If):
            # 4. Ignore nodes located within if TYPE_CHECKING: blocks (AC-4)
            tc_names = ("TYPE_CHECKING",)
            if isinstance(node.test, ast.Name) and node.test.id in tc_names:
                return
            if isinstance(node.test, ast.Attribute) and node.test.attr in tc_names:
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                self._check_resolution(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            # Ignore relative imports as they require complex filesystem resolution
            if (node.level or 0) > 0:
                return
            if not node.module:
                return

            # AC-3: Resolvable via importlib.util.find_spec (Environment check)
            if importlib.util.find_spec(node.module) is not None:
                return

            # AC-1/AC-2: Resolve against symbols in the runbook session
            for alias in node.names:
                if alias.name not in session_symbols:
                    unresolved.add(f"from {node.module} import {alias.name}")

        def _check_resolution(self, module_name: str):
            # Check if module is in runbook or environment
            if module_name in session_symbols:
                return
            if importlib.util.find_spec(module_name) is None:
                unresolved.add(module_name)

    ResolutionVisitor().visit(tree)

    # 6. Log resolution failures using ADR-046 compliant telemetry
    if unresolved:
        unresolved_list = sorted(list(unresolved))
        logger.warning(
            "test_import_resolution_fail",
            extra={"file": file_path, "unresolved_symbols": unresolved_list},
        )
        # Format: "from module import name" => "module.name" for readability
        qualified = [
            s.replace("from ", "").replace(" import ", ".") if s.startswith("from ") else s
            for s in unresolved_list
        ]
        return (
            "IMPORT RESOLUTION FAILURE\n"
            f"UNRESOLVABLE IMPORTS in `{file_path}`:\n"
            + "\n".join(f"  - {q}" for q in qualified)
            + "\n\nThe listed symbols/modules do not exist on disk and were not found "
            "in the current runbook session. If these are internal components, ensure "
            "they are implemented in a #### [NEW] block before importing them in tests."
        )

    return None


# ---------------------------------------------------------------------------
# Full-file apply
# ---------------------------------------------------------------------------


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
    from agent.core.config import resolve_repo_path

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
            from agent.core.implement.guards import FileSizeGuardViolation
            raise FileSizeGuardViolation(
                f"File '{filepath}' already exists and new content is {existing_lines} lines. "
                f"Maximum allowed for full-file replace is {FILE_SIZE_GUARD_THRESHOLD} LOC. "
                "Hint: Update runbook step to use <<<SEARCH/===/>>> blocks for incremental changes, "
                "or pass --legacy-apply to bypass."
            )

    # Idempotency: if file exists with identical content, skip
    if file_path.exists():
        existing_content = file_path.read_text()
        if existing_content.strip() == content.strip():
            logging.info(
                "apply_change_already_applied file=%s", filepath,
            )
            _console.print(
                f"[dim]⏭️  {filepath} already has identical content — skipping[/dim]"
            )
            if span_ctx:
                span_ctx.set_attribute("success", True)
                span_ctx.set_attribute("skipped", True)
                span_ctx.end()
            return True

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
        log_file = resolve_repo_path(".agent/logs/implement_changes.log")
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


# ---------------------------------------------------------------------------
# Runbook linting helpers
# ---------------------------------------------------------------------------


def autocorrect_runbook_fences(content: str) -> Tuple[str, List[str]]:
    """Auto-correct common fence issues in generated runbooks.

    Fixes:
    - Missing blank lines before/after code fences
    - Unbalanced fences

    Args:
        content: Raw runbook markdown.

    Returns:
        Tuple of (corrected_content, list_of_corrections).
    """
    import re as _re
    corrections = []

    # Fix: ensure blank line before opening fence
    fixed = _re.sub(r'([^\n])\n(```)', r'\1\n\n\2', content)
    if fixed != content:
        corrections.append("Added blank lines before code fences")
        content = fixed

    # Fix: ensure blank line after closing fence
    fixed = _re.sub(r'(```)\n([^\n])', r'\1\n\n\2', content)
    if fixed != content:
        corrections.append("Added blank lines after code fences")
        content = fixed

    # Fix: demote non-Step ### headers to bold text
    # AI often generates sub-headers like ### Troubleshooting, ### 1. Foo
    # that the parser treats as empty steps with 0 operations.
    def _demote_non_step(match):
        """Demote non-step headers to bold text."""
        header_text = match.group(1).strip()
        if _re.match(r'^Step \d+', header_text):
            return match.group(0)  # keep actual steps
        return f'**{header_text}**'

    fixed = _re.sub(r'^### (.+)$', _demote_non_step, content, flags=_re.MULTILINE)
    if fixed != content:
        original_count = len(_re.findall(r'^### ', content, _re.MULTILINE))
        fixed_count = len(_re.findall(r'^### ', fixed, _re.MULTILINE))
        demoted = original_count - fixed_count
        corrections.append(f"Demoted {demoted} non-step ### headers to bold text")
        content = fixed

    return content, corrections


def lint_runbook_syntax(content: str) -> List[str]:
    """Check runbook for common syntax issues.

    Args:
        content: Runbook markdown content.

    Returns:
        List of error strings. Empty if no issues found.
    """
    import re as _re
    errors = []

    # Check for balanced fences
    fence_count = len(_re.findall(r'^```', content, _re.MULTILINE))
    if fence_count % 2 != 0:
        errors.append(f"Unbalanced code fences: {fence_count} fence markers (expected even)")

    # Check for __name__ rendered as **name**
    if '**name**' in content or '**main**' in content:
        errors.append("Detected markdown-corrupted Python dunder: **name** or **main** (should be __name__ or __main__)")

    return errors
