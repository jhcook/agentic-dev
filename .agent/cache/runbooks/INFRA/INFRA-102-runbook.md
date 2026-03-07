# INFRA-102: Decompose Implement Command

## State

ACCEPTED

## Goal Description

`commands/implement.py` has grown to 1,976 LOC and conflates three orthogonal concerns: CLI surface (Typer argument parsing), orchestration logic (step execution, parse/apply, retry), and circuit-breaker enforcement (LOC tracking, follow-up story generation). This runbook extracts those concerns into focused modules under `core/implement/` so each can be tested in isolation, while keeping the public API of `commands/implement.py` backwards-compatible so no existing test changes are required.

## Linked Journeys

- JRN-045: Implement Story from Runbook
- JRN-072: Terminal Console TUI Chat

## Panel Review Findings

### @Architect
- `core/implement/` must not import from `commands/` (one-way dependency).
- `commands/implement.py` must re-export every symbol currently imported by existing test files (`count_edit_distance`, `_create_follow_up_story`, `_update_or_create_plan`, `_micro_commit_step`) so tests pass without modification.
- `core/implement/__init__.py` must expose the full public API for future callers.

### @QA
- AC-5 is the hardest constraint: zero changes to `tests/commands/test_implement.py` or any other existing test file.
- New tests in `tests/core/implement/` must be isolated (no subprocess, no filesystem mocks unless strictly necessary).
- Negative test: circuit breaker must halt at 400 cumulative LOC and return a valid follow-up story ID.

### @Security
- `_create_follow_up_story` calls `scrub_sensitive_data` before writing — must be preserved in the new module.
- No PII must appear in structured log fields.

### @Observability
- All OTel spans (`implement.micro_commit_step`, `implement.circuit_breaker`, `implement.apply_change`, `implement.inject_source_context`, `implement.parse_search_replace`) must be retained in their respective new homes.

## Codebase Introspection

### Target File Signatures (from source)

```
# commands/implement.py  (1976 LOC)
MAX_EDIT_DISTANCE_PER_STEP = 30
LOC_WARNING_THRESHOLD = 200
LOC_CIRCUIT_BREAKER_THRESHOLD = 400
FILE_SIZE_GUARD_THRESHOLD = 200
SOURCE_CONTEXT_MAX_LOC = 300
SOURCE_CONTEXT_HEAD_TAIL = 100

def parse_code_blocks(content: str) -> List[Dict[str, str]]
def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]
def backup_file(file_path: Path) -> Optional[Path]
def enforce_docstrings(filepath: str, content: str) -> List[str]
def find_file_in_repo(filename: str) -> List[str]
def get_current_branch() -> str
def is_git_dirty() -> bool
def sanitize_branch_name(title: str) -> str
def count_edit_distance(original: str, modified: str) -> int
def _create_follow_up_story(original_story_id, original_title, remaining_chunks, completed_step_count, cumulative_loc) -> Optional[str]
def _update_or_create_plan(original_story_id, follow_up_story_id, original_title) -> None
def _micro_commit_step(story_id, step_index, step_loc, cumulative_loc, modified_files) -> bool
def create_branch(story_id: str, title: str)
def find_directories_in_repo(dirname: str) -> List[str]
def resolve_path(filepath: str) -> Optional[Path]
def extract_modify_files(runbook_content: str) -> List[str]
def build_source_context(file_paths: List[str]) -> str
def apply_search_replace_to_file(filepath, blocks, yes=False) -> tuple[bool, str]
def apply_change_to_file(filepath, content, yes=False, legacy_apply=False) -> bool
def split_runbook_into_chunks(content: str) -> tuple[str, List[str]]
def extract_story_id(runbook_id: str, runbook_content: str) -> str
def implement(...) -> None   # Typer command, lines 1128-1975
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/commands/test_implement_circuit_breaker.py` | `agent.commands.implement.count_edit_distance` | unchanged (re-exported) | None |
| `tests/commands/test_implement_circuit_breaker.py` | `agent.commands.implement._create_follow_up_story` | unchanged (re-exported) | None |
| `tests/commands/test_implement_circuit_breaker.py` | `agent.commands.implement._micro_commit_step` | unchanged (re-exported) | None |
| `tests/commands/test_implement_circuit_breaker.py` | `agent.commands.implement._update_or_create_plan` | unchanged (re-exported) | None |
| `tests/commands/test_implement.py` | `agent.commands.implement.implement` | unchanged | None |
| `tests/core/implement/test_circuit_breaker.py` | NEW | `agent.core.implement.circuit_breaker` | Create |
| `tests/core/implement/test_orchestrator.py` | NEW | `agent.core.implement.orchestrator` | Create |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| LOC warning threshold | `LOC_WARNING_THRESHOLD` | 200 | Yes |
| Circuit breaker halt | `LOC_CIRCUIT_BREAKER_THRESHOLD` | 400 | Yes |
| Max edit distance/step | `MAX_EDIT_DISTANCE_PER_STEP` | 30 | Yes |
| Safe-apply file size guard | `FILE_SIZE_GUARD_THRESHOLD` | 200 | Yes |
| block_loc bug (AC-9) | chunking loop line ~1606 | `block_loc = 0` set inside `if success:` only | Fix: initialise before apply |

## Targeted Refactors & Cleanups

- [x] Fix `block_loc` uninitialised-variable bug (AC-9): in the full-file code-block apply loop, `block_loc` is only assigned inside `if success:`, so a failed apply carries the previous iteration's value into `step_loc`. Initialise it to `0` before each apply call.
- [x] Move circuit-breaker constants and logic to `core/implement/circuit_breaker.py`.
- [x] Move `enforce_docstrings` and safe-apply guard to `core/implement/guards.py`.
- [x] Move parse/apply helpers and the step-execution body to `core/implement/orchestrator.py`.

## Implementation Steps

### Step 1: Create the core/implement package __init__

#### [NEW] .agent/src/agent/core/implement/__init__.py

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

"""Public API for the core implement package.

Re-exports the symbols that external callers (including the CLI facade
and existing test files) depend on, so import paths are stable across
the decomposition.
"""

from agent.core.implement.circuit_breaker import (
    CircuitBreaker,
    count_edit_distance,
    create_follow_up_story,
    update_or_create_plan,
    micro_commit_step,
    MAX_EDIT_DISTANCE_PER_STEP,
    LOC_WARNING_THRESHOLD,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
)
from agent.core.implement.guards import (
    enforce_docstrings,
    apply_change_to_file,
    apply_search_replace_to_file,
    backup_file,
    FILE_SIZE_GUARD_THRESHOLD,
)
from agent.core.implement.orchestrator import (
    Orchestrator,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
)

__all__ = [
    "CircuitBreaker",
    "Orchestrator",
    "count_edit_distance",
    "create_follow_up_story",
    "update_or_create_plan",
    "micro_commit_step",
    "enforce_docstrings",
    "apply_change_to_file",
    "apply_search_replace_to_file",
    "backup_file",
    "parse_code_blocks",
    "parse_search_replace_blocks",
    "split_runbook_into_chunks",
    "MAX_EDIT_DISTANCE_PER_STEP",
    "LOC_WARNING_THRESHOLD",
    "LOC_CIRCUIT_BREAKER_THRESHOLD",
    "FILE_SIZE_GUARD_THRESHOLD",
]
```

### Step 2: Create circuit_breaker module

#### [NEW] .agent/src/agent/core/implement/circuit_breaker.py

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

"""Micro-commit circuit breaker for the implement command (INFRA-095).

Tracks cumulative lines-of-code edited across runbook steps and enforces
thresholds: a warning at LOC_WARNING_THRESHOLD and a hard halt with
follow-up story generation at LOC_CIRCUIT_BREAKER_THRESHOLD.
"""

import difflib
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

from agent.core.config import config
from agent.core.utils import get_next_id, scrub_sensitive_data

# ---------------------------------------------------------------------------
# Thresholds (INFRA-095)
# ---------------------------------------------------------------------------

MAX_EDIT_DISTANCE_PER_STEP: int = 30
LOC_WARNING_THRESHOLD: int = 200
LOC_CIRCUIT_BREAKER_THRESHOLD: int = 400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_branch_name(title: str) -> str:
    """Sanitize a story title for use in a git branch name."""
    name = title.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')


def count_edit_distance(original: str, modified: str) -> int:
    """Count line-level edit distance between two file contents.

    Uses unified-diff additions + deletions. Both empty strings returns 0.

    Args:
        original: Original file content (empty string for new files).
        modified: Modified file content.

    Returns:
        Number of lines changed (additions + deletions).
    """
    if not original and not modified:
        return 0
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, mod_lines, lineterm="")
    total = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            total += 1
        elif line.startswith("-") and not line.startswith("---"):
            total += 1
    return total


def micro_commit_step(
    story_id: str,
    step_index: int,
    step_loc: int,
    cumulative_loc: int,
    modified_files: List[str],
) -> bool:
    """Create a micro-commit save point for a single implementation step.

    Stages modified files and creates an atomic commit. Non-fatal on failure.

    Args:
        story_id: Story ID for the commit message.
        step_index: 1-based step index.
        step_loc: Lines changed in this step.
        cumulative_loc: Total lines changed so far.
        modified_files: Repo-relative file paths modified in this step.

    Returns:
        True if commit succeeded, False otherwise.
    """
    if not modified_files:
        return True
    try:
        subprocess.run(
            ["git", "add"] + modified_files,
            check=True, capture_output=True, timeout=30,
        )
        commit_msg = (
            f"feat({story_id}): implement step {step_index} "
            f"[{step_loc} LOC, {cumulative_loc} cumulative]"
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True, timeout=30,
        )
        logging.info(
            "save_point story=%s step=%d step_loc=%d cumulative_loc=%d",
            story_id, step_index, step_loc, cumulative_loc,
        )
        return True
    except subprocess.CalledProcessError as exc:
        logging.warning(
            "save_point_failed story=%s step=%d error=%s",
            story_id, step_index, exc,
        )
        return False


def create_follow_up_story(
    original_story_id: str,
    original_title: str,
    remaining_chunks: List[str],
    completed_step_count: int,
    cumulative_loc: int,
) -> Optional[str]:
    """Auto-generate a follow-up story when the circuit breaker activates.

    Creates a COMMITTED story referencing the remaining runbook steps.

    Args:
        original_story_id: Story ID that triggered the circuit breaker.
        original_title: Human-readable title of the original story.
        remaining_chunks: Unprocessed runbook chunk strings.
        completed_step_count: Number of steps already completed.
        cumulative_loc: LOC count at circuit breaker activation.

    Returns:
        New story ID if created successfully, None on failure.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    scope_dir = config.stories_dir / prefix
    scope_dir.mkdir(parents=True, exist_ok=True)
    new_story_id = get_next_id(scope_dir, prefix)

    remaining_summary = "\n".join(
        f"- Step {completed_step_count + i + 1}: {chunk[:200].strip()}"
        for i, chunk in enumerate(remaining_chunks)
    )
    content = f"""# {new_story_id}: {original_title} (Continuation)

## State

COMMITTED

## Problem Statement

Circuit breaker activated during implementation of {original_story_id} at {cumulative_loc} LOC cumulative.
This follow-up story contains the remaining implementation steps.

## User Story

As a **developer**, I want **the remaining steps from {original_story_id} implemented** so that **the full feature is completed across atomic PRs**.

## Acceptance Criteria

- [ ] Complete remaining implementation steps from {original_story_id} runbook.

## Remaining Steps from {original_story_id}

{remaining_summary}

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Related Stories

- {original_story_id} (parent — circuit breaker continuation)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation

## Impact Analysis Summary

Components touched: See remaining steps above.
Workflows affected: /implement
Risks: None beyond standard implementation risks.

## Test Strategy

- Follow the test strategy from the original {original_story_id} runbook.

## Rollback Plan

Revert changes from this follow-up story. The partial work from {original_story_id} remains intact.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
    safe_title = sanitize_branch_name(f"{original_title}-continuation")
    filename = f"{new_story_id}-{safe_title}.md"
    file_path = scope_dir / filename
    if file_path.exists():
        logging.error(
            "follow_up_story_collision path=%s story=%s", file_path, new_story_id
        )
        return None
    try:
        file_path.write_text(scrub_sensitive_data(content))
        logging.info(
            "follow_up_story_created story=%s parent=%s remaining_steps=%d",
            new_story_id, original_story_id, len(remaining_chunks),
        )
        return new_story_id
    except Exception as exc:
        logging.error("Failed to create follow-up story: %s", exc)
        return None


def update_or_create_plan(
    original_story_id: str,
    follow_up_story_id: str,
    original_title: str,
) -> None:
    """Link original and follow-up stories in a Plan document.

    Appends the follow-up to an existing plan that references the original
    story; otherwise creates a minimal new plan linking both.

    Args:
        original_story_id: The original story ID.
        follow_up_story_id: The newly created follow-up story ID.
        original_title: Human-readable title.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    plans_scope_dir = config.plans_dir / prefix
    plans_scope_dir.mkdir(parents=True, exist_ok=True)
    existing_plan = None
    if plans_scope_dir.exists():
        for plan_file in plans_scope_dir.glob("*.md"):
            try:
                if original_story_id in plan_file.read_text():
                    existing_plan = plan_file
                    break
            except Exception:
                continue
    if existing_plan:
        try:
            plan_content = existing_plan.read_text()
            append_text = (
                f"\n- {follow_up_story_id}: {original_title} "
                f"(Continuation — circuit breaker split)\n"
            )
            existing_plan.write_text(plan_content + append_text)
        except Exception as exc:
            logging.warning("Failed to update existing plan %s: %s", existing_plan, exc)
    else:
        plan_path = plans_scope_dir / f"{original_story_id}-plan.md"
        plan_content = f"""# Plan: {original_title}

## Stories

- {original_story_id}: {original_title} (partial — circuit breaker activated)
- {follow_up_story_id}: {original_title} (Continuation)

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
        try:
            plan_path.write_text(plan_content)
        except Exception as exc:
            logging.warning("Failed to create plan: %s", exc)


class CircuitBreaker:
    """Stateful circuit breaker tracking cumulative LOC across runbook steps.

    Usage::

        cb = CircuitBreaker()
        cb.record(step_loc)
        if cb.should_warn():
            ...
        if cb.should_halt():
            ...
    """

    def __init__(self) -> None:
        """Initialise with zero cumulative LOC."""
        self.cumulative_loc: int = 0

    def record(self, step_loc: int) -> None:
        """Add step_loc to cumulative total.

        Args:
            step_loc: Lines changed in the current step.
        """
        self.cumulative_loc += step_loc

    def should_warn(self) -> bool:
        """Return True when the warning threshold has been reached but not breached."""
        return LOC_WARNING_THRESHOLD <= self.cumulative_loc < LOC_CIRCUIT_BREAKER_THRESHOLD

    def should_halt(self) -> bool:
        """Return True when the circuit breaker threshold has been reached."""
        return self.cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD
```

### Step 3: Create guards module

#### [NEW] .agent/src/agent/core/implement/guards.py

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

"""Pre-apply validation gates for the implement command (INFRA-096, INFRA-100).

Provides docstring enforcement (AC-10) and safe-apply file-size guards
(AC-9) that run before any file is written to disk.
"""

import difflib
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.syntax import Syntax

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

# ---------------------------------------------------------------------------
# Thresholds (INFRA-096)
# ---------------------------------------------------------------------------

FILE_SIZE_GUARD_THRESHOLD: int = 200
SOURCE_CONTEXT_MAX_LOC: int = 300
SOURCE_CONTEXT_HEAD_TAIL: int = 100

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
            _console.print(
                f"\n[bold red]❌ Rejected full-file overwrite for {filepath} "
                f"({existing_lines} LOC > {FILE_SIZE_GUARD_THRESHOLD} threshold).[/bold red]"
            )
            logging.warning(
                "apply_change apply_mode=rejected file=%s file_loc=%d threshold=%d",
                filepath, existing_lines, FILE_SIZE_GUARD_THRESHOLD,
            )
            if span_ctx:
                span_ctx.set_attribute("success", False)
                span_ctx.end()
            return False

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
```

### Step 4: Create orchestrator module

#### [NEW] .agent/src/agent/core/implement/orchestrator.py

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

"""Orchestrator for the implement command step-execution loop (INFRA-102).

Contains block parsers, path resolution, source-context injection,
and the per-step apply+commit loop. The CLI facade delegates to
:class:`Orchestrator` after handling argument parsing.
"""

import logging
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

_console = Console()

COMMON_FILES = {"__init__.py", "main.py", "config.py", "utils.py", "conftest.py"}
TRUSTED_ROOT_PREFIXES = (".agent/", "agent/", "backend/", "web/", "mobile/")


def _find_file_in_repo(filename: str) -> List[str]:
    """Return tracked git paths whose basename matches filename.

    Args:
        filename: Basename to search for.

    Returns:
        List of repo-relative paths matching the basename.
    """
    try:
        result = subprocess.check_output(
            ["git", "ls-files", "*" + filename], stderr=subprocess.DEVNULL
        ).decode().strip()
        return result.split("\n") if result else []
    except Exception:
        return []


def _find_directories_in_repo(dirname: str) -> List[str]:
    """Search for directories with a specific name in the repo.

    Excludes .git, node_modules, and dist to prevent false positives.

    Args:
        dirname: Directory basename to search for.

    Returns:
        List of repo-relative directory paths.
    """
    try:
        cmd = [
            "find", ".",
            "-path", "./.git", "-prune",
            "-o", "-path", "*/node_modules", "-prune",
            "-o", "-path", "*/dist", "-prune",
            "-o", "-type", "d", "-name", dirname, "-print",
        ]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return [p.lstrip("./") for p in result.split("\n") if p] if result else []
    except Exception:
        return []


def resolve_path(filepath: str) -> Optional[Path]:
    """Resolve a file path to a real location, with fuzzy fallback.

    Resolution order:

    1. Exact match — return as-is.
    2. Single unique file match in repo — auto-redirect.
    3. New file with trusted root prefix — trust the full path.
    4. New file with unknown prefix — fuzzy-search directory by directory.

    Args:
        filepath: Repo-relative file path (may be AI-generated).

    Returns:
        Resolved :class:`pathlib.Path`, or ``None`` if ambiguous/invalid.
    """
    file_path = Path(filepath)
    if file_path.exists():
        return file_path

    if file_path.name not in COMMON_FILES:
        candidates = _find_file_in_repo(file_path.name)
        exact = [c for c in candidates if Path(c).name == file_path.name]
        if len(exact) == 1:
            new_path = exact[0]
            if new_path != filepath:
                _console.print(f"[yellow]⚠️  Path Auto-Correct (File): '{filepath}' -> '{new_path}'[/yellow]")
            return Path(new_path)
        if len(exact) > 1:
            _console.print(f"[bold red]❌ Ambiguous file path '{filepath}'. Found {len(exact)} matches.[/bold red]")
            return None

    parts = file_path.parts
    current_check = Path(".")
    is_trusted = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)

    for i, part in enumerate(parts[:-1]):
        next_check = current_check / part
        if not next_check.exists():
            if is_trusted:
                return file_path
            _console.print(f"[dim]Directory '{next_check}' not found; searching for '{part}'...[/dim]")
            dir_candidates = _find_directories_in_repo(str(part))
            if len(dir_candidates) == 0:
                _console.print(f"[bold red]❌ Cannot resolve directory '{part}'.[/bold red]")
                return None
            if len(dir_candidates) == 1:
                rest = Path(*parts[i + 1:])
                new_full = Path(dir_candidates[0]) / rest
                _console.print(f"[yellow]⚠️  Path Auto-Correct (Dir): '{filepath}' -> '{new_full}'[/yellow]")
                return new_full
            _console.print(f"[bold red]❌ Ambiguous directory '{part}'. Found {len(dir_candidates)} matches.[/bold red]")
            return None
        current_check = next_check

    return file_path


def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """Parse full-file code blocks from AI-generated markdown.

    Recognises two formats::

        ```python:path/to/file.py
        code
        ```

        File: path/to/file.py
        ```python
        code
        ```

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'`` and ``'content'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    for match in re.finditer(r'```[\w]+:([\w/\.\-_]+)\n(.*?)```', content, re.DOTALL):
        blocks.append({"file": match.group(1).strip(), "content": match.group(2).strip()})
    p2 = r'(?:File|Modify|Create):\s*`?([^\n`]+)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = match.group(1).strip()
        if not any(b["file"] == fp for b in blocks):
            blocks.append({"file": fp, "content": match.group(2).strip()})
    return blocks


def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]:
    """Parse search/replace blocks from AI-generated content.

    Expected format per file::

        File: path/to/file.py
        <<<SEARCH
        exact lines
        ===
        replacement lines
        >>>

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'``, ``'search'``, ``'replace'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    file_sections = re.split(
        r'(?:^|\n)(?:File|Modify):\s*`?([^\n`]+)`?\s*\n',
        content, flags=re.IGNORECASE,
    )
    for i in range(1, len(file_sections), 2):
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        for match in re.finditer(r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', body, re.DOTALL):
            blocks.append({"file": filepath, "search": match.group(1), "replace": match.group(2)})
    if _tracer:
        span = _tracer.start_span("implement.parse_search_replace")
        span.set_attribute("block_count", len(blocks))
        span.end()
    return blocks


def extract_modify_files(runbook_content: str) -> List[str]:
    """Scan a runbook for [MODIFY] markers and return referenced file paths.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Deduplicated list of file path strings in order of first appearance.
    """
    seen: set = set()
    result: List[str] = []
    for path in re.findall(r'\[MODIFY\]\s*`?([^\n`]+)`?', runbook_content, re.IGNORECASE):
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def build_source_context(file_paths: List[str]) -> str:
    """Build a source-context string from current file contents.

    Files exceeding SOURCE_CONTEXT_MAX_LOC are truncated to head/tail sections.

    Args:
        file_paths: Repo-relative paths to include.

    Returns:
        Formatted string containing file contents for prompt injection.
    """
    from agent.core.implement.guards import SOURCE_CONTEXT_MAX_LOC, SOURCE_CONTEXT_HEAD_TAIL

    def _inner() -> str:
        """Read, optionally truncate, and format each file."""
        parts: List[str] = []
        for filepath in file_paths:
            resolved = resolve_path(filepath)
            if not resolved or not resolved.exists():
                logging.warning("source_context_skip file=%s reason=not_found", filepath)
                continue
            try:
                content = resolved.read_text()
            except Exception as exc:
                logging.warning("source_context_skip file=%s reason=%s", filepath, exc)
                continue
            lines = content.splitlines()
            loc = len(lines)
            if loc > SOURCE_CONTEXT_MAX_LOC:
                head = "\n".join(lines[:SOURCE_CONTEXT_HEAD_TAIL])
                tail = "\n".join(lines[-SOURCE_CONTEXT_HEAD_TAIL:])
                omitted = loc - 2 * SOURCE_CONTEXT_HEAD_TAIL
                truncated = f"{head}\n... ({omitted} lines omitted) ...\n{tail}"
                parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC — truncated):\n```\n{truncated}\n```\n"
                )
            else:
                parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC):\n```\n{content}\n```\n"
                )
        return "\n".join(parts)

    if _tracer:
        with _tracer.start_as_current_span("implement.inject_source_context") as span:
            span.set_attribute("file_count", len(file_paths))
            result = _inner()
            span.set_attribute("total_chars", len(result))
            return result
    return _inner()


def split_runbook_into_chunks(content: str) -> Tuple[str, List[str]]:
    """Split a runbook into a global context header and per-step chunks.

    Also appends Definition of Done and Verification Plan as trailing chunks
    so documentation and test requirements are processed by the AI.

    Args:
        content: Full runbook markdown string.

    Returns:
        Tuple of ``(global_context, list_of_step_chunks)``.
    """
    impl_headers = ["## Implementation Steps", "## Proposed Changes", "## Changes"]
    start_idx = -1
    for header in impl_headers:
        if header in content:
            start_idx = content.find(header)
            break
    if start_idx == -1:
        return content, [content]
    global_context = content[:start_idx].strip()
    body = content[start_idx:]
    raw_chunks = re.split(r'\n### ', body)
    header_part = raw_chunks[0]
    chunks: List[str] = [
        f"{header_part}\n### {raw_chunks[i]}" for i in range(1, len(raw_chunks))
    ]
    if not chunks:
        chunks = [body]
    dod = re.search(r'(## Definition of Done.*?)(?=\n## |$)', content, re.DOTALL)
    if dod:
        chunks.append(f"DOCUMENTATION AND COMPLETION REQUIREMENTS:\n{dod.group(1).strip()}")
    verify = re.search(r'(## Verification Plan.*?)(?=\n## |$)', content, re.DOTALL)
    if verify:
        chunks.append(f"TEST REQUIREMENTS:\n{verify.group(1).strip()}")
    return global_context, chunks


class Orchestrator:
    """Executes runbook steps: parse blocks, enforce guards, micro-commit.

    Delegates file writing to :mod:`agent.core.implement.guards` and LOC
    tracking/thresholds to :class:`~agent.core.implement.circuit_breaker.CircuitBreaker`.
    """

    def __init__(self, story_id: str, yes: bool = False, legacy_apply: bool = False) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []

    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        Processes search/replace blocks first, then full-file blocks.
        For each full-file block runs the docstring gate (AC-10) before
        writing. Fixes the block_loc uninitialised-variable bug (AC-9) by
        resetting ``block_loc`` to ``0`` before each apply call.

        Args:
            chunk_result: Raw AI output for this step.
            step_index: 1-based step number (for logging).

        Returns:
            Tuple of ``(step_loc, step_modified_files)``.
        """
        from agent.core.implement.guards import (
            apply_search_replace_to_file,
            apply_change_to_file,
            enforce_docstrings,
        )
        from agent.core.implement.circuit_breaker import count_edit_distance

        step_loc = 0
        step_modified_files: List[str] = []

        sr_blocks = parse_search_replace_blocks(chunk_result)
        sr_handled: set = set()
        if sr_blocks:
            sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for block in sr_blocks:
                sr_by_file[block["file"]].append(block)
            for sr_filepath, file_blocks in sr_by_file.items():
                fp = Path(sr_filepath)
                original_content = fp.read_text() if fp.exists() else ""
                success, final_content = apply_search_replace_to_file(
                    sr_filepath, file_blocks, self.yes
                )
                if success:
                    step_loc += count_edit_distance(original_content, final_content)
                    step_modified_files.append(sr_filepath)
                    sr_handled.add(sr_filepath)

        code_blocks = [b for b in parse_code_blocks(chunk_result) if b["file"] not in sr_handled]
        for block in code_blocks:
            violations = enforce_docstrings(block["file"], block["content"])
            if violations:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold red]❌ DOCSTRING GATE: {block['file']} rejected "
                    f"({len(violations)} violation(s)):[/bold red]"
                )
                for v in violations:
                    _console.print(f"   [red]• {v}[/red]")
                continue

            fp = Path(block["file"])
            original_content = fp.read_text() if fp.exists() else ""

            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            success = apply_change_to_file(
                block["file"], block["content"], self.yes,
                legacy_apply=self.legacy_apply,
            )
            if success:
                block_loc = count_edit_distance(original_content, block["content"])
                step_modified_files.append(block["file"])
            else:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold yellow]⚠️  INCOMPLETE STEP: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            step_loc += block_loc

        self.run_modified_files.extend(step_modified_files)
        return step_loc, step_modified_files

    def print_incomplete_summary(self) -> None:
        """Print the INCOMPLETE IMPLEMENTATION banner when files were rejected.

        Must be called before post-apply governance gates so the developer
        sees the full picture regardless of gate outcomes (AC-9).
        """
        if self.rejected_files:
            _console.print(
                f"\n[bold red]🚨 INCOMPLETE IMPLEMENTATION "
                f"— {len(self.rejected_files)} file(s) NOT applied:[/bold red]"
            )
            for rf in self.rejected_files:
                _console.print(f"  [red]• {rf}[/red]")
            _console.print(
                "[yellow]Hint: update runbook step(s) to use "
                "<<<SEARCH\n<exact lines>\n===\n<replacement>\n>>> blocks "
                "then re-run `agent implement`.[/yellow]"
            )
            logging.warning(
                "implement_incomplete story=%s rejected_files=%r",
                self.story_id, self.rejected_files,
            )
```

### Step 5: Create test package __init__ files

#### [NEW] .agent/tests/core/__init__.py

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
"""Test package for agent.core modules."""
```

#### [NEW] .agent/tests/core/implement/__init__.py

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
"""Test package for agent.core.implement modules."""
```

### Step 6: Create circuit_breaker unit tests

#### [NEW] .agent/tests/core/implement/test_circuit_breaker.py

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

"""Tests for core.implement.circuit_breaker (AC-7, Negative Test)."""

import subprocess
from unittest.mock import patch

import pytest

from agent.core.implement.circuit_breaker import (
    CircuitBreaker,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
    LOC_WARNING_THRESHOLD,
    count_edit_distance,
    create_follow_up_story,
    micro_commit_step,
    update_or_create_plan,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker thresholds and state transitions."""

    def test_initial_state(self):
        """Starts at zero cumulative LOC."""
        cb = CircuitBreaker()
        assert cb.cumulative_loc == 0

    def test_record_accumulates(self):
        """record() sums step LOC into cumulative total."""
        cb = CircuitBreaker()
        cb.record(50)
        cb.record(100)
        assert cb.cumulative_loc == 150

    def test_should_warn_at_threshold(self):
        """should_warn() is True at exactly LOC_WARNING_THRESHOLD."""
        cb = CircuitBreaker()
        cb.record(LOC_WARNING_THRESHOLD)
        assert cb.should_warn() is True

    def test_should_not_warn_below_threshold(self):
        """should_warn() is False below warning threshold."""
        cb = CircuitBreaker()
        cb.record(LOC_WARNING_THRESHOLD - 1)
        assert cb.should_warn() is False

    def test_should_halt_at_breaker_threshold(self):
        """Negative test: should_halt() activates at LOC_CIRCUIT_BREAKER_THRESHOLD (400)."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD)
        assert cb.should_halt() is True

    def test_should_not_halt_below_threshold(self):
        """should_halt() is False below circuit breaker threshold."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD - 1)
        assert cb.should_halt() is False

    def test_warn_is_false_at_halt_threshold(self):
        """should_warn() is False once should_halt() is True."""
        cb = CircuitBreaker()
        cb.record(LOC_CIRCUIT_BREAKER_THRESHOLD)
        assert cb.should_warn() is False


class TestCountEditDistance:
    """Tests for count_edit_distance."""

    def test_unchanged_returns_zero(self):
        """Identical strings produce zero edit distance."""
        c = "line1\nline2\n"
        assert count_edit_distance(c, c) == 0

    def test_added_line(self):
        """Added line is counted."""
        assert count_edit_distance("a\n", "a\nb\n") == 1

    def test_deleted_line(self):
        """Deleted line is counted."""
        assert count_edit_distance("a\nb\n", "a\n") == 1

    def test_both_empty(self):
        """Both empty strings produce zero."""
        assert count_edit_distance("", "") == 0

    def test_new_file(self):
        """New file (empty original) counts all added lines."""
        assert count_edit_distance("", "a\nb\n") == 2


class TestMicroCommitStep:
    """Tests for micro_commit_step."""

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_success(self, mock_run):
        """Returns True and makes two git calls."""
        assert micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"]) is True
        assert mock_run.call_count == 2

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_failure_non_fatal(self, mock_run):
        """Returns False without raising on git failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert micro_commit_step("INFRA-001", 1, 10, 10, ["file.py"]) is False

    @patch("agent.core.implement.circuit_breaker.subprocess.run")
    def test_empty_files_skips_git(self, mock_run):
        """Returns True immediately when no files to commit."""
        assert micro_commit_step("INFRA-001", 1, 0, 0, []) is True
        mock_run.assert_not_called()


class TestCreateFollowUpStory:
    """Tests for create_follow_up_story."""

    @patch("agent.core.implement.circuit_breaker.get_next_id", return_value="INFRA-999")
    @patch("agent.core.implement.circuit_breaker.config")
    def test_creates_committed_story(self, mock_config, _mock_id, tmp_path):
        """Created story has COMMITTED state and references the original."""
        mock_config.stories_dir = tmp_path / "stories"
        story_id = create_follow_up_story("INFRA-001", "Test Feature", ["Step 2"], 1, 450)
        assert story_id == "INFRA-999"
        files = list((tmp_path / "stories" / "INFRA").glob("INFRA-999-*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "## State\n\nCOMMITTED" in content
        assert "INFRA-001" in content

    @patch("agent.core.implement.circuit_breaker.get_next_id", return_value="INFRA-999")
    @patch("agent.core.implement.circuit_breaker.config")
    def test_no_overwrite_existing(self, mock_config, _mock_id, tmp_path):
        """Returns None when target story file already exists (collision guard)."""
        mock_config.stories_dir = tmp_path / "stories"
        target = tmp_path / "stories" / "INFRA"
        target.mkdir(parents=True)
        (target / "INFRA-999-test-feature-continuation.md").write_text("existing")
        assert create_follow_up_story("INFRA-001", "Test Feature", ["Step 2"], 1, 450) is None
```

### Step 7: Create orchestrator unit tests

#### [NEW] .agent/tests/core/implement/test_orchestrator.py

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

"""Tests for core.implement.orchestrator (AC-7)."""

import pytest

from agent.core.implement.orchestrator import (
    Orchestrator,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
)


class TestParseCodeBlocks:
    """Tests for parse_code_blocks."""

    def test_fenced_language_colon_format(self):
        """Parses ```language:path format."""
        blocks = parse_code_blocks("```python:src/foo.py\ncode here\n```")
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/foo.py"
        assert blocks[0]["content"] == "code here"

    def test_file_header_format(self):
        """Parses 'File: path' header format."""
        blocks = parse_code_blocks("File: src/bar.py\n```python\ncode\n```")
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/bar.py"

    def test_no_blocks_returns_empty(self):
        """Returns empty list when no code blocks found."""
        assert parse_code_blocks("no blocks here") == []


class TestParseSearchReplaceBlocks:
    """Tests for parse_search_replace_blocks."""

    def test_parses_single_block(self):
        """Parses a single search/replace block."""
        content = "File: src/foo.py\n<<<SEARCH\nold line\n===\nnew line\n>>>"
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["file"] == "src/foo.py"
        assert blocks[0]["search"] == "old line"
        assert blocks[0]["replace"] == "new line"

    def test_multiple_blocks_same_file(self):
        """Parses multiple blocks under a single file header."""
        content = (
            "File: src/foo.py\n"
            "<<<SEARCH\na\n===\nb\n>>>\n"
            "<<<SEARCH\nc\n===\nd\n>>>"
        )
        blocks = parse_search_replace_blocks(content)
        assert len(blocks) == 2
        assert all(b["file"] == "src/foo.py" for b in blocks)

    def test_no_blocks_returns_empty(self):
        """Returns empty list when no search/replace blocks found."""
        assert parse_search_replace_blocks("nothing here") == []


class TestSplitRunbookIntoChunks:
    """Tests for split_runbook_into_chunks."""

    def test_splits_on_step_headers(self):
        """Each ### Step N becomes its own chunk."""
        content = (
            "## Overview\npreamble\n"
            "## Implementation Steps\n\n"
            "### Step 1\ncontent1\n"
            "### Step 2\ncontent2"
        )
        global_ctx, chunks = split_runbook_into_chunks(content)
        assert "preamble" in global_ctx
        assert len(chunks) == 2
        assert "Step 1" in chunks[0]
        assert "Step 2" in chunks[1]

    def test_no_impl_header_returns_full_content(self):
        """When no implementation section header found, returns one chunk."""
        _, chunks = split_runbook_into_chunks("# Just a doc\nsome text")
        assert len(chunks) == 1

    def test_dod_appended_as_chunk(self):
        """Definition of Done section is appended as a final chunk."""
        content = (
            "## Implementation Steps\n\n### Step 1\ncode\n"
            "## Definition of Done\n- [ ] CHANGELOG updated"
        )
        _, chunks = split_runbook_into_chunks(content)
        assert any("CHANGELOG" in c for c in chunks)


class TestOrchestrator:
    """Tests for Orchestrator.apply_chunk."""

    def test_apply_chunk_new_file(self, tmp_path, monkeypatch):
        """New-file blocks are written and step_loc is non-zero."""
        monkeypatch.chdir(tmp_path)
        orch = Orchestrator("INFRA-001", yes=True)
        chunk = (
            'File: new_module.py\n'
            '```python\n'
            '"""New module."""\n\n\ndef foo():\n    """Foo."""\n    pass\n'
            '```'
        )
        step_loc, modified = orch.apply_chunk(chunk, step_index=1)
        assert "new_module.py" in modified
        assert step_loc > 0

    def test_apply_chunk_docstring_violation_rejected(self, tmp_path, monkeypatch):
        """Files missing docstrings are added to rejected_files, not written."""
        monkeypatch.chdir(tmp_path)
        orch = Orchestrator("INFRA-001", yes=True)
        chunk = "File: bad_module.py\n```python\ndef foo():\n    pass\n```"
        _, modified = orch.apply_chunk(chunk, step_index=1)
        assert "bad_module.py" in orch.rejected_files
        assert modified == []
```

### Step 8: Add re-exports to commands/implement.py facade

#### [MODIFY] .agent/src/agent/commands/implement.py

```
<<<SEARCH
from agent.core.config import config
from agent.core.utils import (
    find_runbook_file,
    scrub_sensitive_data,
)
from agent.core.context import context_loader
from agent.commands.utils import update_story_state
from agent.commands import gates
from agent.core.utils import get_next_id
===
from agent.core.config import config
from agent.core.utils import (
    find_runbook_file,
    scrub_sensitive_data,
    get_next_id,
)
from agent.core.context import context_loader
from agent.commands.utils import update_story_state
from agent.commands import gates

# ---------------------------------------------------------------------------
# Re-export core symbols so existing tests (that import from
# agent.commands.implement) continue to work without modification (AC-5).
# ---------------------------------------------------------------------------
from agent.core.implement.circuit_breaker import (  # noqa: F401
    count_edit_distance,
    create_follow_up_story as _create_follow_up_story,
    update_or_create_plan as _update_or_create_plan,
    micro_commit_step as _micro_commit_step,
    MAX_EDIT_DISTANCE_PER_STEP,
    LOC_WARNING_THRESHOLD,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
)
from agent.core.implement.guards import (  # noqa: F401
    enforce_docstrings,
    backup_file,
    apply_search_replace_to_file,
    apply_change_to_file,
    FILE_SIZE_GUARD_THRESHOLD,
    SOURCE_CONTEXT_MAX_LOC,
    SOURCE_CONTEXT_HEAD_TAIL,
)
from agent.core.implement.orchestrator import (  # noqa: F401
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
    extract_modify_files,
    build_source_context,
    resolve_path,
    _find_file_in_repo as find_file_in_repo,
    _find_directories_in_repo as find_directories_in_repo,
)
>>>
```

## Verification Plan

### Automated Tests

- [ ] `cd .agent && python -m pytest tests/commands/test_implement.py tests/commands/test_implement_circuit_breaker.py tests/commands/test_implement_safe_apply.py tests/commands/test_implement_pathing.py tests/commands/test_implement_branching.py -v` — all existing command tests pass without modification (AC-5).
- [ ] `cd .agent && python -m pytest tests/core/implement/ -v` — all new core tests pass (AC-7).
- [ ] `python -c "import agent.cli"` — exits cleanly with no circular import errors (AC-6).

### Manual Verification

- [ ] `cd .agent && python -m pytest tests/ -q` — full suite green.
- [ ] `wc -l .agent/src/agent/core/implement/*.py` — no individual file exceeds 500 LOC.

## Definition of Done

### Documentation

- [ ] `CHANGELOG.md` updated under `[Unreleased]` describing the decomposition of `commands/implement.py` into `core/implement/`.

### Observability

- [ ] OTel spans (`implement.micro_commit_step`, `implement.circuit_breaker`, `implement.apply_change`, `implement.inject_source_context`, `implement.parse_search_replace`) all retained in their new modules.
- [ ] All new `logging` calls use structured `key=value` format; no PII in log fields.

### Testing

- [ ] All existing tests pass without modification (AC-5).
- [ ] New tests cover: `CircuitBreaker` thresholds, `count_edit_distance`, `micro_commit_step`, `create_follow_up_story`, `parse_code_blocks`, `parse_search_replace_blocks`, `split_runbook_into_chunks`, `Orchestrator.apply_chunk`.
- [ ] Negative test: `CircuitBreaker.should_halt()` returns `True` at exactly 400 LOC cumulative.
- [ ] Negative test: `Orchestrator.apply_chunk` rejects file into `rejected_files` when docstring gate fails.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
