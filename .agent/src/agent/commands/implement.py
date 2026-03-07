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

import difflib
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

# from agent.core.ai import ai_service # Moved to local import
from agent.core.config import config
from agent.core.utils import (
    find_runbook_file,
    scrub_sensitive_data,
)
from agent.core.context import context_loader
from agent.commands.utils import update_story_state
from agent.commands import gates
from agent.core.utils import get_next_id

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # Graceful degradation if OTel not installed

# Micro-Commit Circuit Breaker Thresholds (INFRA-095)
MAX_EDIT_DISTANCE_PER_STEP = 30
LOC_WARNING_THRESHOLD = 200
LOC_CIRCUIT_BREAKER_THRESHOLD = 400

# Safe Apply Thresholds (INFRA-096)
FILE_SIZE_GUARD_THRESHOLD = 200   # LOC — reject full-file overwrite above this
SOURCE_CONTEXT_MAX_LOC = 300      # LOC — truncate source context above this
SOURCE_CONTEXT_HEAD_TAIL = 100    # LOC — lines to keep from head/tail when truncating

app = typer.Typer()
console = Console()

def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """
    Parse code blocks from AI-generated markdown content.
    
    Looks for patterns like:
    ```python:path/to/file.py
    code here
    ```
    
    Or simpler format:
    File: path/to/file.py
    ```python
    code here
    ```
    
    Returns:
        List of dicts with 'file' and 'content' keys
    """
    blocks = []
    
    # Pattern 1: ```language:filepath
    pattern1 = r'```[\w]+:([\w/\.\-_]+)\n(.*?)```'
    for match in re.finditer(pattern1, content, re.DOTALL):
        filepath = match.group(1).strip()
        code = match.group(2).strip()
        blocks.append({'file': filepath, 'content': code})
    
    # Pattern 2: File: filepath followed by code block
    pattern2 = r'(?:File|Modify|Create):\s*`?([^\n`]+)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(pattern2, content, re.DOTALL | re.IGNORECASE):
        filepath = match.group(1).strip()
        code = match.group(2).strip()
        # Avoid duplicates
        if not any(b['file'] == filepath for b in blocks):
            blocks.append({'file': filepath, 'content': code})
    
    return blocks


def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]:
    """
    Parse search/replace blocks from AI-generated content.

    Expected format (per file):
        File: path/to/file.py
        <<<SEARCH
        exact lines to find
        ===
        replacement lines
        >>>

    Multiple blocks per file are supported.

    Returns:
        List of dicts with 'file', 'search', 'replace' keys.
    """
    blocks = []

    # Split content by File: headers
    file_sections = re.split(
        r'(?:^|\n)(?:File|Modify):\s*`?([^\n`]+)`?\s*\n',
        content,
        flags=re.IGNORECASE,
    )

    # file_sections alternates: [preamble, filepath1, body1, filepath2, body2, ...]
    for i in range(1, len(file_sections), 2):
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""

        # Find all <<<SEARCH ... === ... >>> blocks in this file's body
        sr_pattern = r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>'
        for match in re.finditer(sr_pattern, body, re.DOTALL):
            search_text = match.group(1)
            replace_text = match.group(2)
            blocks.append({
                'file': filepath,
                'search': search_text,
                'replace': replace_text,
            })

    # OTel span for observability
    if tracer:
        span = tracer.start_span("implement.parse_search_replace")
        span.set_attribute("block_count", len(blocks))
        span.end()

    return blocks


def backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup of a file before modification."""
    if not file_path.exists():
        return None
    
    backup_dir = Path(".agent/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.name}.backup-{timestamp}"
    backup_path = backup_dir / backup_name
    
    shutil.copy2(file_path, backup_path)
    return backup_path


def enforce_docstrings(filepath: str, content: str) -> List[str]:
    """Check generated Python source for missing PEP-257 docstrings.

    Inspects every module, class, and function/method definition (including
    inner functions such as decorator closures) and returns a list of
    human-readable violation strings.  Non-Python files always pass.

    Args:
        filepath: Repo-relative path of the file being generated.
        content: The Python source code string to validate.

    Returns:
        A list of violation strings, e.g.
        ["streaming.py: decorator() is missing a docstring"].  Empty list
        means the content passes.
    """
    import ast

    if not filepath.endswith(".py"):
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Syntax errors are caught by the QA gate; don't double-report here.
        return []

    violations: List[str] = []
    filename = Path(filepath).name

    def _has_docstring(node: ast.AST) -> bool:
        """Return True if node's first statement is a string literal."""
        return (
            bool(getattr(node, "body", None))
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)  # type: ignore[attr-defined]
            and isinstance(node.body[0].value.value, str)      # type: ignore[attr-defined]
        )

    # Module-level docstring
    if not _has_docstring(tree):
        violations.append(f"{filename}: module is missing a docstring")

    # Walk all class/function definitions (includes inner functions)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _has_docstring(node):
                violations.append(
                    f"{filename}: {node.name}() is missing a docstring"
                )
        elif isinstance(node, ast.ClassDef):
            if not _has_docstring(node):
                violations.append(
                    f"{filename}: class {node.name} is missing a docstring"
                )

    return violations

import subprocess


def find_file_in_repo(filename: str) -> List[str]:
    """
    Search for a file in the git repo (respecting .gitignore).
    Returns list of matching relative paths.
    """
    try:
        # Search for the filename anywhere in the tracked files
        result = subprocess.check_output(
            ["git", "ls-files", "*"+filename], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if not result:
            return []
        return result.split('\n')
    except Exception:
        return []

def get_current_branch() -> str:
    """Get the current git branch name."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""

def is_git_dirty() -> bool:
    """Check if there are uncommitted changes."""
    try:
        # Check for modified filed
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], 
            stderr=subprocess.DEVNULL
        ).strip()
        return bool(status)
    except Exception:
        return True # Fail safe

def sanitize_branch_name(title: str) -> str:
    """Sanitize a story title for use in a branch name."""
    # Lowercase, replace special chars with hyphen
    name = title.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')


def count_edit_distance(original: str, modified: str) -> int:
    """Count the line-level edit distance between two file contents.

    Uses a simple diff-based approach: counts lines that are added or removed.
    Binary files or empty comparisons return 0.

    # TODO(INFRA-096): Update to also accept search/replace block format
    # once diff-based apply lands.

    Args:
        original: Original file content (empty string for new files).
        modified: Modified file content.

    Returns:
        Number of lines changed (additions + deletions).
    """
    if not original and not modified:
        return 0

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(original_lines, modified_lines, lineterm="")
    edit_count = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            edit_count += 1
        elif line.startswith("-") and not line.startswith("---"):
            edit_count += 1

    return edit_count


def _create_follow_up_story(
    original_story_id: str,
    original_title: str,
    remaining_chunks: List[str],
    completed_step_count: int,
    cumulative_loc: int,
) -> Optional[str]:
    """Auto-generate a follow-up story for remaining runbook steps.

    Called when the circuit breaker activates. Creates a COMMITTED story
    referencing the remaining implementation steps.

    Args:
        original_story_id: The story ID that triggered the circuit breaker.
        original_title: Human-readable title of the original story.
        remaining_chunks: List of unprocessed runbook chunk strings.
        completed_step_count: Number of steps already completed.
        cumulative_loc: LOC count at circuit breaker activation.

    Returns:
        The new story ID if created successfully, None otherwise.
    """
    # Determine scope prefix from original story ID
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    scope_dir = config.stories_dir / prefix
    scope_dir.mkdir(parents=True, exist_ok=True)

    new_story_id = get_next_id(scope_dir, prefix)

    # Build remaining steps summary
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

    # Guard: never overwrite an existing story file (Panel recommendation)
    if file_path.exists():
        logging.error(
            "follow_up_story_collision path=%s story=%s",
            file_path, new_story_id,
        )
        return None

    try:
        file_path.write_text(scrub_sensitive_data(content))
        logging.info(
            "follow_up_story_created story=%s parent=%s remaining_steps=%d",
            new_story_id, original_story_id, len(remaining_chunks),
        )
        return new_story_id
    except Exception as e:
        logging.error("Failed to create follow-up story: %s", e)
        return None


def _update_or_create_plan(
    original_story_id: str,
    follow_up_story_id: str,
    original_title: str,
) -> None:
    """Link original and follow-up stories in a Plan document.

    If a Plan already exists referencing the original story, appends the
    follow-up. Otherwise, creates a minimal Plan linking both.

    Args:
        original_story_id: The original story ID.
        follow_up_story_id: The newly created follow-up story ID.
        original_title: Human-readable title.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    plans_scope_dir = config.plans_dir / prefix
    plans_scope_dir.mkdir(parents=True, exist_ok=True)

    # Search for existing plan referencing original story
    existing_plan = None
    if plans_scope_dir.exists():
        for plan_file in plans_scope_dir.glob("*.md"):
            try:
                plan_content = plan_file.read_text()
                if original_story_id in plan_content:
                    existing_plan = plan_file
                    break
            except Exception:
                continue

    if existing_plan:
        # Append follow-up to existing plan
        try:
            plan_content = existing_plan.read_text()
            append_text = (
                f"\n- {follow_up_story_id}: {original_title} "
                f"(Continuation — circuit breaker split)\n"
            )
            existing_plan.write_text(plan_content + append_text)
            console.print(f"[dim]📎 Updated existing plan: {existing_plan.name}[/dim]")
        except Exception as e:
            logging.warning("Failed to update existing plan %s: %s", existing_plan, e)
    else:
        # Create minimal plan
        plan_filename = f"{original_story_id}-plan.md"
        plan_path = plans_scope_dir / plan_filename
        plan_content = f"""# Plan: {original_title}

## Stories

- {original_story_id}: {original_title} (partial — circuit breaker activated)
- {follow_up_story_id}: {original_title} (Continuation)

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
        try:
            plan_path.write_text(plan_content)
            console.print(f"[dim]📎 Created plan linking stories: {plan_path.name}[/dim]")
        except Exception as e:
            logging.warning("Failed to create plan: %s", e)


def _micro_commit_step(
    story_id: str,
    step_index: int,
    step_loc: int,
    cumulative_loc: int,
    modified_files: List[str],
) -> bool:
    """Create a micro-commit save point for a single implementation step.

    Stages modified files and creates an atomic commit. Returns False if
    the git operation fails (non-fatal — logged and skipped).

    Args:
        story_id: Story ID for the commit message.
        step_index: 1-based step index.
        step_loc: Lines changed in this step.
        cumulative_loc: Total lines changed so far.
        modified_files: List of file paths modified in this step.

    Returns:
        True if commit succeeded, False otherwise.
    """
    if not modified_files:
        return True

    try:
        # Stage modified files
        subprocess.run(
            ["git", "add"] + modified_files,
            check=True, capture_output=True, timeout=30,
        )

        # Create atomic commit
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

    except subprocess.CalledProcessError as e:
        logging.warning(
            "save_point_failed story=%s step=%d error=%s",
            story_id, step_index, e,
        )
        console.print(f"[yellow]⚠️  Save-point commit failed for step {step_index}: {e}[/yellow]")
        return False


def create_branch(story_id: str, title: str):
    """Create or checkout a feature branch."""
    branch_name = f"{story_id}/{sanitize_branch_name(title)}"
    
    # Check if exists
    exists = False
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", branch_name], 
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        exists = True
    except subprocess.CalledProcessError:
        exists = False
        
    if exists:
        console.print(f"[bold blue]🔄 Switching to existing branch: {branch_name}[/bold blue]")
        subprocess.run(["git", "checkout", branch_name], check=True)
    else:
        console.print(f"[bold green]🌱 Creating new branch: {branch_name}[/bold green]")
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)
    
    # Log event
    log_file = Path(".agent/logs/implement.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] Branch{'Switched' if exists else 'Created'}: {branch_name}\n")

def find_directories_in_repo(dirname: str) -> List[str]:
    """Search for directories with a specific name in the repo.

    Excludes ``.git``, ``node_modules``, and ``dist`` to prevent false-positive
    matches inside the web frontend dependency tree (e.g. dozens of
    ``node_modules/*/src`` entries that make common names ambiguous).

    Args:
        dirname: Directory base name to search for.

    Returns:
        List of repo-relative directory paths matching *dirname*.
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
        if not result:
            return []
        paths = [p.lstrip("./") for p in result.split("\n") if p]
        return paths
    except Exception:
        return []

def resolve_path(filepath: str) -> Optional[Path]:
    """
    Resolve a potentially hallucinated file path to a real location.
    Returns None if the path is invalid/ambiguous and should be rejected.
    Returns Path object if resolved.
    """
    file_path = Path(filepath)
    
    # Files that are too common to guess "moves" for.
    # If the exact path doesn't exist, we assume the AI meant to create a new file
    # rather than modifying an existing __init__.py somewhere random in the repo.
    COMMON_FILES = {"__init__.py", "main.py", "config.py", "utils.py", "conftest.py"}

    # 1. Exact Match (Best Case)
    if file_path.exists():
        return file_path
        
    # 2. Existing File Search (renames/moves)
    # If the file exists somewhere else with the exact same name, assume that's it.
    
    # Skip fuzzy search for common files to prevent massive ambiguity/false positives
    if file_path.name in COMMON_FILES:
        candidates = []
    else:
        candidates = find_file_in_repo(file_path.name)
        
    exact_matches = [c for c in candidates if Path(c).name == file_path.name]
    
    if len(exact_matches) == 1:
        # Single exact file match - Auto-Redirect
        new_path = exact_matches[0]
        if new_path != filepath:
            console.print(f"[yellow]⚠️  Path Auto-Correct (File Match): '{filepath}' -> '{new_path}'[/yellow]")
            return Path(new_path)
    elif len(exact_matches) > 1:
        # Ambiguous file match
        console.print(f"[bold red]❌ Ambiguous file path '{filepath}'. Found multiple existing files:[/bold red]")
        for i, c in enumerate(exact_matches):
            console.print(f"  {i+1}: {c}")
        console.print("[red]Aborting to prevent editing the wrong file.[/red]")
        return None

    # 3. Smart Directory Resolution (New File)
    # The file is new. Check if the directory path is valid.
    # We walk the path parts. If we hit a non-existent directory, we try to resolve it.
    parts = file_path.parts
    current_check = Path(".")

    # Known root prefixes that are unambiguous — never fuzzy-search within these.
    # Prevents '.agent/src/agent/core/governance/' from matching web/components/governance.
    TRUSTED_ROOT_PREFIXES = (
        ".agent/",
        "agent/",
        "backend/",
        "web/",
        "mobile/",
    )
    is_trusted_root = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)

    for i, part in enumerate(parts[:-1]): # Skip filename
        next_check = current_check / part
        if not next_check.exists():
            if is_trusted_root:
                # Path starts with a known repo root — trust the full path and
                # let the caller create the directory (apply_change_to_file does mkdir -p).
                # Do NOT fuzzy-search for the missing component.
                return file_path

            # Fallback fuzzy search only for paths without a trusted root prefix.
            console.print(f"[dim]Directory '{next_check}' not found. Searching for '{part}'...[/dim]")
            dir_candidates = find_directories_in_repo(str(part))

            if len(dir_candidates) == 0:
                console.print(f"[bold red]❌ Cannot create new root hierarchy '{next_check}'.[/bold red]")
                console.print(f"[red]Directory '{part}' not found in repo.[/red]")
                return None
            elif len(dir_candidates) == 1:
                # Unique match found! Resolve the prefix.
                found_dir = dir_candidates[0]
                rest_of_path = Path(*parts[i+1:])
                new_full_path = Path(found_dir) / rest_of_path
                console.print(f"[yellow]⚠️  Path Auto-Correct (Dir Match): '{filepath}' -> '{new_full_path}'[/yellow]")
                return new_full_path
            else:
                # Ambiguous directory
                console.print(f"[bold red]❌ Ambiguous directory '{part}'. Found multiple matches:[/bold red]")
                for i, c in enumerate(dir_candidates[:10]):
                    console.print(f"  - {c}")
                console.print("[red]Aborting. Please specify the full path.[/red]")
                return None

        current_check = next_check

    return file_path


def extract_modify_files(runbook_content: str) -> List[str]:
    """
    Scan runbook content for [MODIFY] markers and extract file paths.

    Looks for patterns like:
        #### [MODIFY] .agent/src/agent/commands/implement.py

    Returns:
        List of file path strings referenced by [MODIFY] markers.
    """
    pattern = r'\[MODIFY\]\s*`?([^\n`]+)`?'
    matches = re.findall(pattern, runbook_content, re.IGNORECASE)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for path in matches:
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def build_source_context(file_paths: List[str]) -> str:
    """
    Build source context string by reading current file contents.

    Files exceeding SOURCE_CONTEXT_MAX_LOC are truncated to
    first/last SOURCE_CONTEXT_HEAD_TAIL lines with an omission marker.

    Args:
        file_paths: List of repo-relative file paths to read.

    Returns:
        Formatted string containing file contents for prompt injection.
    """
    def _inner():
        context_parts = []

        for filepath in file_paths:
            resolved = resolve_path(filepath)
            if not resolved or not resolved.exists():
                logging.warning(
                    "source_context_skip file=%s reason=not_found", filepath
                )
                continue

            try:
                content = resolved.read_text()
            except Exception as e:
                logging.warning(
                    "source_context_skip file=%s reason=%s", filepath, e
                )
                continue

            lines = content.splitlines()
            loc = len(lines)

            if loc > SOURCE_CONTEXT_MAX_LOC:
                head = "\n".join(lines[:SOURCE_CONTEXT_HEAD_TAIL])
                tail = "\n".join(lines[-SOURCE_CONTEXT_HEAD_TAIL:])
                omitted = loc - (2 * SOURCE_CONTEXT_HEAD_TAIL)
                truncated_content = (
                    f"{head}\n"
                    f"... ({omitted} lines omitted) ...\n"
                    f"{tail}"
                )
                context_parts.append(
                    f"### Current content of `{filepath}` "
                    f"({loc} LOC — truncated):\n"
                    f"```\n{truncated_content}\n```\n"
                )
            else:
                context_parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC):\n"
                    f"```\n{content}\n```\n"
                )

        return "\n".join(context_parts)

    if tracer:
        with tracer.start_as_current_span("implement.inject_source_context") as span:
            span.set_attribute("file_count", len(file_paths))
            result = _inner()
            span.set_attribute("total_chars", len(result))
            return result
    return _inner()


def apply_search_replace_to_file(
    filepath: str,
    blocks: List[Dict[str, str]],
    yes: bool = False,
) -> tuple[bool, str]:
    """
    Apply search/replace blocks surgically to an existing file.

    Each block must match exactly. If any block fails to match,
    the entire operation is aborted — no partial apply.

    Args:
        filepath: Repo-relative file path.
        blocks: List of dicts with 'search' and 'replace' keys.
        yes: Skip confirmation prompts.

    Returns:
        Tuple of (success: bool, final_content: str).
        On failure, final_content is the original unchanged content.
    """
    # OTel span for observability
    span_ctx = None
    if tracer:
        span_ctx = tracer.start_span("implement.apply_change")
        span_ctx.set_attribute("file", filepath)
        span_ctx.set_attribute("apply_mode", "search_replace")

    resolved_path = resolve_path(filepath)
    if not resolved_path or not resolved_path.exists():
        console.print(
            f"[bold red]❌ Cannot apply search/replace to "
            f"'{filepath}': file not found.[/bold red]"
        )
        return False, ""

    original_content = resolved_path.read_text()
    working_content = original_content

    # Dry-run: verify all blocks match before applying any
    for i, block in enumerate(blocks):
        if block['search'] not in working_content:
            console.print(
                f"[bold red]❌ Search block {i+1}/{len(blocks)} "
                f"not found in {filepath}.[/bold red]"
            )
            console.print(
                f"[dim]Expected to find:[/dim]\n"
                f"[red]{block['search'][:200]}...[/red]"
            )
            logging.warning(
                "search_replace_match_failure file=%s block=%d/%d",
                filepath, i + 1, len(blocks),
            )
            return False, original_content

        # Warn if search text is ambiguous (appears multiple times)
        match_count = working_content.count(block['search'])
        if match_count > 1:
            console.print(
                f"[yellow]⚠️  Search block {i+1} matches "
                f"{match_count} locations in {filepath}. "
                f"Replacing first occurrence only.[/yellow]"
            )
            logging.warning(
                "search_replace_ambiguous file=%s block=%d/%d "
                "match_count=%d",
                filepath, i + 1, len(blocks), match_count,
            )

        # Apply this block to working content (for subsequent matches)
        working_content = working_content.replace(
            block['search'], block['replace'], 1
        )

    # Show diff preview
    console.print(f"\n[bold cyan]📝 Search/Replace for: {filepath}[/bold cyan]")
    console.print(
        f"[dim]Applying {len(blocks)} search/replace block(s)[/dim]"
    )

    # Show unified diff (uses module-level difflib import)
    diff_lines = list(difflib.unified_diff(
        original_content.splitlines(keepends=True),
        working_content.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    ))
    if diff_lines:
        diff_text = "".join(diff_lines)
        syntax = Syntax(diff_text, "diff", theme="monokai")
        console.print(syntax)

    # Confirmation
    if not yes:
        response = typer.confirm(
            f"\nApply {len(blocks)} search/replace block(s) to "
            f"{filepath}?",
            default=False,
        )
        if not response:
            console.print("[yellow]⏭️  Skipped[/yellow]")
            return False, original_content

    # Backup and write
    backup_path = backup_file(resolved_path)
    if backup_path:
        console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")

    try:
        resolved_path.write_text(working_content)
        console.print(
            f"[bold green]✅ Applied {len(blocks)} search/replace "
            f"block(s) to {filepath}[/bold green]"
        )

        # Structured logging (NFR)
        logging.info(
            "apply_change apply_mode=search_replace file=%s "
            "blocks=%d lines_changed=%d",
            filepath, len(blocks),
            count_edit_distance(original_content, working_content),
        )

        # Log the change
        log_file = Path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat()
        with open(log_file, "a") as f:
            f.write(
                f"[{timestamp}] SearchReplace: {filepath} "
                f"({len(blocks)} blocks)\n"
            )

        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True, working_content
    except Exception as e:
        console.print(
            f"[bold red]❌ Failed to write file: {e}[/bold red]"
        )
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
    """
    Apply code changes to a file with smart path resolution.

    For existing files exceeding FILE_SIZE_GUARD_THRESHOLD, rejects
    full-file overwrites unless legacy_apply is True (AC-5).
    """
    # OTel span for observability
    span_ctx = None
    if tracer:
        span_ctx = tracer.start_span("implement.apply_change")
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

    # AC-5: File size guard for existing files
    if file_path.exists() and not legacy_apply:
        try:
            existing_lines = len(file_path.read_text().splitlines())
        except Exception:
            existing_lines = 0

        if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
            console.print(
                f"\n[bold red]❌ Rejected full-file overwrite for "
                f"{filepath} ({existing_lines} LOC > "
                f"{FILE_SIZE_GUARD_THRESHOLD} threshold).[/bold red]"
            )
            console.print(
                "[yellow]The AI must use search/replace format for "
                "large existing files, or use --legacy-apply to "
                "bypass.[/yellow]"
            )
            logging.warning(
                "apply_change apply_mode=rejected file=%s "
                "file_loc=%d threshold=%d",
                filepath, existing_lines, FILE_SIZE_GUARD_THRESHOLD,
            )
            return False

    # Show diff preview
    console.print(f"\n[bold cyan]📝 Changes for: {filepath}[/bold cyan]")
    
    if file_path.exists():
        console.print("[yellow]File exists. Showing new content:[/yellow]")
    else:
        console.print("[green]New file will be created.[/green]")
    
    # Show code with syntax highlighting
    syntax = Syntax(content, "python" if filepath.endswith(".py") else "text", 
                   theme="monokai", line_numbers=True)
    console.print(syntax)
    
    # Confirmation
    if not yes:
        response = typer.confirm(f"\nApply changes to {filepath}?", default=False)
        if not response:
            console.print("[yellow]⏭️  Skipped[/yellow]")
            return False
    
    # Backup existing file
    if file_path.exists():
        backup_path = backup_file(file_path)
        if backup_path:
            console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")
    
    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Write new content
        file_path.write_text(content)
        console.print(f"[bold green]✅ Applied changes to {filepath}[/bold green]")
        
        # Apply license header if applicable
        from agent.commands.license import apply_license_to_file
        if apply_license_to_file(file_path):
            console.print(f"[dim]Added copyright header to {filepath}[/dim]")

        # Structured logging (NFR — INFRA-096)
        logging.info(
            "apply_change apply_mode=full_file file=%s "
            "lines_changed=%d",
            filepath, len(content.splitlines()),
        )
        
        # Log the change
        log_file = Path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat()
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] Modified: {filepath}\n")
            
        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True
    except Exception as e:
        console.print(f"[bold red]❌ Failed to write file: {e}[/bold red]")
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False

def split_runbook_into_chunks(content: str) -> tuple[str, List[str]]:
    """
    Splits a runbook into global context and discrete implementation chunks.
    Returns (global_context, task_chunks)
    
    Now includes Definition of Done and Verification Plan as separate chunks
    to ensure documentation and test requirements are processed.
    """
    # Find the start of implementation-related content
    impl_headers = ["## Implementation Steps", "## Proposed Changes", "## Changes"]
    start_idx = -1
    for h in impl_headers:
        if h in content:
            start_idx = content.find(h)
            break
    
    if start_idx == -1:
        return content, [content]

    global_context = content[:start_idx].strip()
    body = content[start_idx:]
    
    # Split the body into chunks by '### '
    raw_chunks = re.split(r'\n### ', body)
    
    chunks = []
    header_part = raw_chunks[0] # e.g. "## Implementation Steps\n..."
    
    for i in range(1, len(raw_chunks)):
        chunks.append(f"{header_part}\n### {raw_chunks[i]}")
    
    if not chunks:
        chunks = [body]
    
    # CRITICAL: Also extract Definition of Done and Verification Plan as final chunks
    # These often contain documentation and test requirements that must be implemented
    dod_match = re.search(r'(## Definition of Done.*?)(?=\n## |$)', content, re.DOTALL)
    if dod_match:
        dod_content = dod_match.group(1).strip()
        chunks.append(f"DOCUMENTATION AND COMPLETION REQUIREMENTS:\n{dod_content}")
        
    verify_match = re.search(r'(## Verification Plan.*?)(?=\n## |$)', content, re.DOTALL)
    if verify_match:
        verify_content = verify_match.group(1).strip()
        chunks.append(f"TEST REQUIREMENTS:\n{verify_content}")
        
    return global_context, chunks


def extract_story_id(runbook_id: str, runbook_content: str) -> str:
    """
    Attempt to find the linked Story ID.
    1. Check if Runbook ID looks like a Story ID (e.g. INFRA-123) and exists.
    2. Parse 'Story: <ID>' or 'Related Story: <ID>' from content.
    """
    from agent.core.utils import find_story_file

    # 1. Try Runbook ID directly (common case)
    if find_story_file(runbook_id):
        return runbook_id

    # 2. Parse from content
    # Look for "Related Story" header and subsequent list items or "Story: XYZ"
    # Simple regex for finding ID patterns in the first 500 chars (metadata section)
    # We look for something that looks like PROJ-123
    
    # Restrict to top of file to avoid false positives in body
    header_section = runbook_content[:1000] 
    
    # Regex for IDs like PROJ-123
    id_matches = re.findall(r"\b[A-Z]+-\d+\b", header_section)
    
    # Filter out the runbook ID itself if it matches
    for candidate in id_matches:
        if candidate != runbook_id and find_story_file(candidate):
            return candidate
            
    return runbook_id # Fallback to using runbook ID as best guess


def implement(
    runbook_id: str = typer.Argument(..., help="The ID of the runbook to implement."),
    apply: bool = typer.Option(
        False, "--apply", help="Apply changes to files automatically."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts (use with --apply)."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Force specific AI model deployment ID."
    ),
    skip_tests: bool = typer.Option(
        False, "--skip-tests", help="Skip QA test gate (audit-logged)."
    ),
    skip_security: bool = typer.Option(
        False, "--skip-security", help="Skip security scan gate (audit-logged)."
    ),
    legacy_apply: bool = typer.Option(
        False, "--legacy-apply",
        help="Bypass safe-apply protections (full-file overwrite allowed). Audit-logged.",
    ),
):
    """
    Execute an implementation runbook using AI with chunked task processing.
    
    By default, generates implementation advice as markdown.
    With --apply, automatically applies code changes to files.
    With --yes, skips confirmation prompts (requires --apply).
    """
    # 0. Configure Provider Override if set
    from agent.core.ai import ai_service  # ADR-025: lazy init
    if provider:
        ai_service.set_provider(provider)
    
    # Validate flag combination
    if yes and not apply:
        console.print("[bold red]❌ --yes requires --apply flag[/bold red]")
        raise typer.Exit(code=1)
    
    # 1. Find Runbook
    runbook_file = find_runbook_file(runbook_id)
    if not runbook_file:
         console.print(
             f"[bold red]❌ Runbook file not found for {runbook_id}[/bold red]"
         )
         raise typer.Exit(code=1)

    console.print(f"🛈 Implementing Runbook {runbook_id}...")
    original_runbook_content = runbook_file.read_text()
    runbook_content_scrubbed = scrub_sensitive_data(original_runbook_content)

    # 1.1 Enforce Runbook State
    # Check for formats: "Status: ACCEPTED", "## Status\nACCEPTED", "## State\nACCEPTED"
    status_pattern = r"(?:^Status:\s*ACCEPTED|^## Status\s*\n+ACCEPTED|^## State\s*\n+ACCEPTED)"
    if not re.search(status_pattern, runbook_content_scrubbed, re.MULTILINE):
        console.print(
            f"[bold red]❌ Runbook {runbook_id} is not ACCEPTED. "
            "Please review and update status to ACCEPTED "
            "before implementing.[/bold red]"
        )
        raise typer.Exit(code=1)

    # 1.1.5 AUTOMATION: Branch Management (INFRA-055)
    
    # Check Dirty State — warn on story branches, block on main
    if is_git_dirty():
        current_branch = get_current_branch()
        if current_branch == "main":
            console.print("[bold red]❌ Uncommitted changes detected on main.[/bold red]")
            console.print("Please stash or commit your changes before starting implementation.")
            raise typer.Exit(code=1)
        else:
            console.print("[yellow]⚠️  Uncommitted changes detected — proceeding on story branch.[/yellow]")

    current_branch = get_current_branch()
    story_id = extract_story_id(runbook_id, runbook_content_scrubbed)
    
    # Get Story Title for branch name
    from agent.core.utils import find_story_file
    story_file = find_story_file(story_id)
    story_title = "feature"
    if story_file:
         # content is # ID: Title
         first_line = story_file.read_text().splitlines()[0]
         # Remove ID prefix if present
         if first_line.startswith(f"# {story_id}:"):
             story_title = first_line.replace(f"# {story_id}:", "").strip()
         elif first_line.startswith("#"):
             story_title = first_line.lstrip("# ").strip()

    if current_branch == "main":
        console.print(f"[dim]On main branch. Setting up workspace for {story_id}...[/dim]")
        create_branch(story_id, story_title)
    elif current_branch.startswith(f"{story_id}/"):
        console.print(f"[bold green]✅ Already on valid story branch: {current_branch}[/bold green]")
    else:
        console.print(f"[bold red]❌ Invalid Branch: {current_branch}[/bold red]")
        console.print(f"You must be on 'main' or a branch starting with '{story_id}/' to implement this story.")
        raise typer.Exit(code=1)


    # 1.2 AUTOMATION: Update Story State (Phase 0)
    story_id = extract_story_id(runbook_id, runbook_content_scrubbed)
    
    # Check if Story is Retired/Deprecated (Enforcement)
    from agent.core.utils import find_story_file
    story_file = find_story_file(story_id)
    if story_file:
         s_content = story_file.read_text()
         s_match = re.search(r"(^## State\s*\n+)([A-Za-z\s]+)", s_content, re.MULTILINE)
         if s_match:
             current_state = s_match.group(2).strip().upper()
             if current_state in ["RETIRED", "DEPRECATED", "SUPERSEDED"]:
                 console.print(f"[bold red]⛔ Cannot implement Story {story_id}: Status is '{current_state}'[/bold red]")
                 raise typer.Exit(code=1)

    # 1.2.5 JOURNEY GATE (INFRA-055)
    from agent.commands.check import validate_linked_journeys  # ADR-025: local import
    journey_result = validate_linked_journeys(story_id)
    if not journey_result["passed"]:
        console.print(f"[bold red]⛔ Journey Gate FAILED for {story_id}: {journey_result['error']}[/bold red]")
        console.print("[dim]Hint: Add real journey IDs (e.g., JRN-044) to 'Linked Journeys' in the story file.[/dim]")
        raise typer.Exit(code=1)
    console.print(f"[green]✅ Journey Gate passed — linked: {', '.join(journey_result['journey_ids'])}[/green]")

    # INFRA-096: Audit log legacy-apply usage
    if legacy_apply:
        gates.log_skip_audit("Safe apply bypass", story_id)
        console.print(
            f"⚠️  [AUDIT] Safe-apply protections bypassed at "
            f"{datetime.now().isoformat()}"
        )

    update_story_state(story_id, "IN_PROGRESS", context_prefix="Phase 0")

    # 2. Load Guide
    guide_path = config.agent_dir / "workflows/implement.md"
    guide_content = ""
    if guide_path.exists():
        guide_content = scrub_sensitive_data(guide_path.read_text())
    
    import asyncio
    ctx = asyncio.run(context_loader.load_context())
    rules_content = ctx.get("rules", "")
    instructions_content = ctx.get("instructions", "")
    adrs_content = ctx.get("adrs", "")
    
    # COMPRESSION: Remove markdown comments and extra blank lines to save token space
    rules_content = re.sub(r'<!--.*?-->', '', rules_content, flags=re.DOTALL)
    rules_content = re.sub(r'\n{3,}', '\n\n', rules_content)

    # 4. Hybrid Strategy: Try Full Context -> Fallback to Chunking
    
    # Load configurable license template
    app_license_template = config.get_app_license_header()
    license_instruction = ""
    if app_license_template:
        license_instruction = f"\n- **CRITICAL**: All new source code files MUST begin with the following exact license header:\n{app_license_template}\n"

    # Attempt 1: Full Context
    console.print("[dim]Attempting full context execution...[/dim]")
    
    full_content = ""
    fallback_needed = False
    
    # Track overall success
    implementation_success = False
    # Track files the safe-apply guard rejected (INFRA-096)
    rejected_files: List[str] = []

    try:
        system_prompt = f"""You are an Implementation Agent.
Your goal is to EXECUTE ALL tasks defined in the provided RUNBOOK, including code, documentation, and tests.

CONTEXT:
1. RUNBOOK (The plan you must follow - ALL sections are mandatory)
2. IMPLEMENTATION GUIDE (The process you must follow)
3. RULES (Governance you must obey)
4. ADRs (Architectural decisions you must respect)

INSTRUCTIONS:
- Review the ENTIRE Runbook, including:
  * 'Proposed Changes' / 'Implementation Steps' - Generate the code
  * 'Definition of Done' - Generate documentation updates (CHANGELOG.md, README.md)
  * 'Verification Plan' - Generate test files
- **CRITICAL**: You MUST generate ALL artifacts specified, not just the main code.
- **IMPORTANT**: Use REPO-RELATIVE paths for all files (e.g., .agent/src/agent/main.py). 
- **WARNING**: DO NOT use 'agent/' as a root folder. The source code lives in '.agent/src/agent/'.
- **IMPORTANT**: Respect all Architectural Decision Records (ADRs). Do not contradict codified decisions.{license_instruction}
- **OUTPUT FORMAT for EXISTING files** — emit search/replace blocks:

File: path/to/existing_file.py
<<<SEARCH
exact lines to find in the current file
===
replacement lines
>>>

You may emit multiple <<<SEARCH...>>> blocks per file.

- **OUTPUT FORMAT for NEW files** — emit complete file content:

File: path/to/new_file.py
```python
# Complete file content here
```

- NEVER emit complete file content for files listed in SOURCE CONTEXT below.
  Use search/replace blocks to make surgical changes.
- Include all necessary imports in your search/replace blocks.
- Documentation files (CHANGELOG.md, README.md) should use search/replace if they already exist.
- Test files should follow the patterns in .agent/tests/.
- **CRITICAL — DOCSTRINGS**: Every module, class, and function/method you produce MUST have a
  PEP-257 docstring. This is enforced by an automated gate — missing docstrings will BLOCK the
  build. Inner functions (e.g. decorator closures) are not exempt.
"""
        # INFRA-096: Inject source context for files being modified
        modify_files = extract_modify_files(runbook_content_scrubbed)
        source_context = ""
        if modify_files:
            source_context = build_source_context(modify_files)
            source_ctx_chars = len(source_context)
            console.print(
                f"[dim]📄 Injected source context for "
                f"{len(modify_files)} file(s) "
                f"({source_ctx_chars} chars)[/dim]"
            )
            # Token budget warning (NFR)
            total_estimate = (
                len(system_prompt) + len(runbook_content_scrubbed)
                + source_ctx_chars + 5000  # overhead estimate
            )
            if total_estimate > 80000:  # ~80% of 100k char window
                logging.warning(
                    "token_budget_warning total_chars=%d "
                    "threshold=80000",
                    total_estimate,
                )
                console.print(
                    f"[yellow]⚠️  Prompt size ({total_estimate} chars) "
                    f"approaching context window limit.[/yellow]"
                )

        user_prompt = f"""RUNBOOK CONTENT:
{runbook_content_scrubbed}

SOURCE CONTEXT (Current file contents for files being modified):
{source_context}

IMPLEMENTATION GUIDE:
{guide_content}

GOVERNANCE RULES:
{rules_content}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}
"""
        # Log context size
        context_size = len(system_prompt) + len(user_prompt)
        logging.info(f"AI Full Context Attempt | Context size: ~{context_size} chars")

        console.print("[bold green]🤖 AI is coding (Full Context)...[/bold green]")
        with console.status("[bold green]🤖 AI is coding (Full Context)...[/bold green]"):
             full_content = ai_service.complete(system_prompt, user_prompt, model=model)
             if not full_content:
                 raise Exception("Empty response from AI")
        
        implementation_success = True

    except Exception as e:
        console.print(f"[yellow]⚠️ Full context failed: {e}[/yellow]")
        console.print("[bold blue]🔄 Falling back to Chunked Processing...[/bold blue]")
        fallback_needed = True

    # Attempt 2: Chunking (Fallback)
    if fallback_needed:
        # Load lean rules (coding only) for fallback — instructions and ADRs still included
        console.print("[yellow]⚠️  Applying semantic context filtering (Coding Rules Only)...[/yellow]")
        
        from agent.core.utils import load_governance_context
        filtered_rules = scrub_sensitive_data(load_governance_context(coding_only=True))
        # Compress (remove comments/extra whitespace)
        filtered_rules = re.sub(r'<!--.*?-->', '', filtered_rules, flags=re.DOTALL)
        filtered_rules = re.sub(r'\n{3,}', '\n\n', filtered_rules)

        global_runbook_context, chunks = split_runbook_into_chunks(runbook_content_scrubbed)
        console.print(f"[dim]Runbook split into {len(chunks)} tasks[/dim]")

        # Reset provider state to ensure chunks use the preferred/forced provider,
        # ignoring any fallback switches that happened during Full Context failure.
        if provider:
             ai_service.set_provider(provider)
        else:
             ai_service.reset_provider()

        cumulative_loc = 0
        run_modified_files: List[str] = []  # all files touched across all steps
        completed_steps = 0

        for idx, chunk in enumerate(chunks):
            if len(chunks) > 1:
                console.print(f"\n[bold blue]🚀 Processing Task {idx+1}/{len(chunks)}...[/bold blue]")

            chunk_system_prompt = f"""You are an Implementation Agent.
Your goal is to EXECUTE a SPECIFIC task from the provided RUNBOOK.
CONSTRAINTS:
1. ONLY implement the changes described in the 'CURRENT TASK'.
2. Maintain consistency with the 'GLOBAL RUNBOOK CONTEXT'.
3. Follow the 'IMPLEMENTATION GUIDE' and 'GOVERNANCE RULES'.
4. **IMPORTANT**: Use REPO-RELATIVE paths (e.g., .agent/src/agent/main.py). DO NOT use 'agent/' as root.{license_instruction}
5. **CRITICAL**: Keep changes small — aim for under {MAX_EDIT_DISTANCE_PER_STEP} lines of edits per step.
OUTPUT FORMAT:
- **For EXISTING files** — use search/replace blocks:

File: path/to/existing_file.py
<<<SEARCH
exact lines to find in the current file
===
replacement lines
>>>

- **For NEW files** — use complete file content:

File: path/to/new_file.py
```python
# Complete file content here
```

- NEVER emit complete file content for files in SOURCE CONTEXT. Use search/replace.
- **CRITICAL — DOCSTRINGS**: Every module, class, and function/method you produce MUST have a
  PEP-257 docstring. Missing docstrings will BLOCK the build. Inner functions are not exempt.
"""
            # INFRA-096: Per-chunk source context
            chunk_modify_files = extract_modify_files(chunk)
            chunk_source_context = ""
            if chunk_modify_files:
                chunk_source_context = build_source_context(
                    chunk_modify_files
                )
                console.print(
                    f"[dim]📄 Source context: "
                    f"{len(chunk_modify_files)} file(s) "
                    f"({len(chunk_source_context)} chars)[/dim]"
                )

            chunk_user_prompt = f"""GLOBAL RUNBOOK CONTEXT (Truncated):
{global_runbook_context[:8000]}

--------------------------------------------------------------------------------
CURRENT TASK:
{chunk}
--------------------------------------------------------------------------------

SOURCE CONTEXT (Current file contents):
{chunk_source_context}

RULES (Filtered):
{filtered_rules}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}
"""
            logging.info(
                "AI Task %d/%d | Context size: ~%d chars",
                idx + 1, len(chunks),
                len(chunk_system_prompt) + len(chunk_user_prompt),
            )

            chunk_result = None
            try:
                console.print(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]")
                with console.status(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]"):
                    chunk_result = ai_service.complete(chunk_system_prompt, chunk_user_prompt, model=model)
            except Exception as e:
                console.print(f"[bold red]❌ Task {idx+1} failed during generation: {e}[/bold red]")
                raise typer.Exit(code=1)

            if not chunk_result:
                continue

            full_content += f"\n\n{chunk_result}"

            # --- Apply and measure edit distance (AC-1, AC-2) ---
            if apply:
                step_loc = 0
                step_modified_files = []

                # --- Apply search/replace blocks first (INFRA-096) ---
                sr_blocks = parse_search_replace_blocks(chunk_result)
                if sr_blocks:
                    # Group blocks by file (uses module-level defaultdict import)
                    sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
                    for block in sr_blocks:
                        sr_by_file[block['file']].append(block)

                    console.print(
                        f"[dim]Found {len(sr_blocks)} search/replace "
                        f"block(s) across {len(sr_by_file)} file(s)[/dim]"
                    )

                    for sr_filepath, file_blocks in sr_by_file.items():
                        file_path = Path(sr_filepath)
                        original_content = ""
                        if file_path.exists():
                            try:
                                original_content = file_path.read_text()
                            except Exception:
                                pass

                        success, final_content = apply_search_replace_to_file(
                            sr_filepath, file_blocks, yes,
                        )

                        if success:
                            block_loc = count_edit_distance(
                                original_content, final_content
                            )
                            step_loc += block_loc
                            step_modified_files.append(sr_filepath)

                # --- Then apply full-file code blocks (existing path) ---
                code_blocks = parse_code_blocks(chunk_result)
                if code_blocks:
                    # Filter out files already handled by search/replace
                    sr_handled = {b['file'] for b in sr_blocks} if sr_blocks else set()
                    code_blocks = [
                        b for b in code_blocks
                        if b['file'] not in sr_handled
                    ]

                    if code_blocks:
                        console.print(
                            f"[dim]Found {len(code_blocks)} full-file "
                            f"block(s) in this task[/dim]"
                        )
                        for block in code_blocks:
                            file_path = Path(block['file'])

                            # Measure edit distance before applying
                            original_content = ""
                            if file_path.exists():
                                try:
                                    original_content = file_path.read_text()
                                except Exception:
                                    pass

                            # --- Pre-apply docstring enforcement (INFRA-100) ---
                            docstring_violations = enforce_docstrings(
                                block['file'], block['content']
                            )
                            if docstring_violations:
                                rejected_files.append(block['file'])
                                console.print(
                                    f"[bold red]❌ DOCSTRING GATE: {block['file']} rejected "
                                    f"({len(docstring_violations)} violation(s)):[/bold red]"
                                )
                                for v in docstring_violations:
                                    console.print(f"   [red]• {v}[/red]")
                                console.print(
                                    "[yellow]   Fix: add PEP-257 docstrings and re-run.[/yellow]"
                                )
                                continue

                            success = apply_change_to_file(
                                block['file'], block['content'], yes,
                                legacy_apply=legacy_apply,
                            )

                            block_loc = 0
                            if success:
                                block_loc = count_edit_distance(original_content, block['content'])
                                step_modified_files.append(block['file'])
                            else:
                                rejected_files.append(block['file'])
                                console.print(
                                    f"[bold yellow]⚠️  INCOMPLETE STEP: "
                                    f"{block['file']} was not applied. "
                                    f"Update the runbook step to use "
                                    f"<<<SEARCH/===/>>> format for this file.[/bold yellow]"
                                )
                            step_loc += block_loc

                # AC-2: Small-step enforcement
                if step_loc > MAX_EDIT_DISTANCE_PER_STEP:
                    console.print(
                        f"[yellow]⚠️  Step {idx+1} exceeded small-step limit: "
                        f"{step_loc} LOC (max {MAX_EDIT_DISTANCE_PER_STEP})[/yellow]"
                    )

                cumulative_loc += step_loc
                completed_steps = idx + 1

                run_modified_files.extend(step_modified_files)

                # AC-1: Save-point commit (with OTel span)
                def _do_micro_commit():
                    _micro_commit_step(
                        story_id, idx + 1, step_loc, cumulative_loc, step_modified_files,
                    )

                if tracer:
                    with tracer.start_as_current_span("implement.micro_commit_step") as span:
                        span.set_attribute("step_index", idx + 1)
                        span.set_attribute("step_loc", step_loc)
                        span.set_attribute("cumulative_loc", cumulative_loc)
                        _do_micro_commit()
                else:
                    _do_micro_commit()

                console.print(
                    f"[green]✅ Step {idx+1} committed "
                    f"({step_loc} LOC this step, {cumulative_loc} LOC cumulative)[/green]"
                )

                # AC-3: LOC warning
                if LOC_WARNING_THRESHOLD <= cumulative_loc < LOC_CIRCUIT_BREAKER_THRESHOLD:
                    console.print(
                        f"[bold yellow]⚠️  Approaching LOC limit: "
                        f"{cumulative_loc}/{LOC_CIRCUIT_BREAKER_THRESHOLD} cumulative[/bold yellow]"
                    )
                    logging.warning(
                        "loc_warning story=%s cumulative_loc=%d threshold=%d",
                        story_id, cumulative_loc, LOC_CIRCUIT_BREAKER_THRESHOLD,
                    )

                # AC-4: Circuit breaker
                if cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD:
                    remaining_chunks = chunks[idx + 1:]

                    def _do_circuit_breaker():
                        nonlocal remaining_chunks
                        logging.warning(
                            "circuit_breaker story=%s cumulative_loc=%d "
                            "completed_steps=%d remaining_steps=%d",
                            story_id, cumulative_loc, completed_steps, len(remaining_chunks),
                        )

                        console.print(
                            f"\n[bold red]🛑 Circuit breaker triggered at "
                            f"{cumulative_loc} LOC (limit: {LOC_CIRCUIT_BREAKER_THRESHOLD}).[/bold red]"
                        )

                        if remaining_chunks:
                            # AC-5: Follow-up story
                            follow_up_id = _create_follow_up_story(
                                story_id, story_title, remaining_chunks,
                                completed_steps, cumulative_loc,
                            )

                            if follow_up_id:
                                console.print(
                                    f"[bold blue]📝 Follow-up story created: {follow_up_id}[/bold blue]"
                                )
                                console.print(
                                    f"[dim]Run: agent new-runbook {follow_up_id}[/dim]"
                                )

                                # AC-6: Plan linkage
                                _update_or_create_plan(story_id, follow_up_id, story_title)

                        console.print(
                            f"[bold green]✅ Partial work committed ({completed_steps} steps).[/bold green]"
                        )
                        console.print(
                            "[dim]Exiting cleanly. Resume with the follow-up story.[/dim]"
                        )

                    if tracer:
                        with tracer.start_as_current_span("implement.circuit_breaker") as span:
                            span.set_attribute("story_id", story_id)
                            span.set_attribute("cumulative_loc", cumulative_loc)
                            span.set_attribute("completed_steps", completed_steps)
                            span.set_attribute("remaining_steps", len(remaining_chunks))
                            _do_circuit_breaker()
                    else:
                        _do_circuit_breaker()

                    raise typer.Exit(code=0)

        # If we made it through the loop, set success status if we have content
        if full_content:
            implementation_success = True

    # Final Handling
    if not full_content:
         console.print("[bold red]❌ All attempts failed.[/bold red]")
         raise typer.Exit(code=1)

    # ... Display/Apply logic for full content ...
    if not apply and full_content:
         console.print(Markdown(full_content))
    elif apply and not fallback_needed: # If we did full context apply, do it now
         console.print("\n[bold blue]🔧 Applying changes...[/bold blue]")

         # INFRA-096: Handle search/replace blocks first
         sr_blocks = parse_search_replace_blocks(full_content)
         if sr_blocks:
             # Uses module-level defaultdict import
             sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
             for block in sr_blocks:
                 sr_by_file[block['file']].append(block)

             for sr_filepath, file_blocks in sr_by_file.items():
                 success, _ = apply_search_replace_to_file(
                     sr_filepath, file_blocks, yes,
                 )
                 if not success:
                     logging.warning(
                         "full_context_sr_failure file=%s blocks=%d",
                         sr_filepath, len(file_blocks),
                     )

         # Then handle full-file code blocks
         sr_handled = {b['file'] for b in sr_blocks} if sr_blocks else set()
         code_blocks = [
             b for b in parse_code_blocks(full_content)
             if b['file'] not in sr_handled
         ]
         for block in code_blocks:
            # --- Pre-apply docstring enforcement (INFRA-100) ---
            fc_docstring_violations = enforce_docstrings(
                block['file'], block['content']
            )
            if fc_docstring_violations:
                rejected_files.append(block['file'])
                console.print(
                    f"[bold red]❌ DOCSTRING GATE: {block['file']} rejected "
                    f"({len(fc_docstring_violations)} violation(s)):[/bold red]"
                )
                for v in fc_docstring_violations:
                    console.print(f"   [red]• {v}[/red]")
                console.print(
                    "[yellow]   Fix: add PEP-257 docstrings and re-run.[/yellow]"
                )
                continue

            fc_success = apply_change_to_file(
                block['file'], block['content'], yes,
                legacy_apply=legacy_apply,
            )
            if not fc_success:
                rejected_files.append(block['file'])
                console.print(
                    f"[bold yellow]⚠️  INCOMPLETE: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            
    # Surface incomplete steps before governance gates so the developer
    # sees the full picture regardless of gate outcomes.
    if rejected_files:
        console.print(
            "\n[bold red]🚨 INCOMPLETE IMPLEMENTATION "
            f"— {len(rejected_files)} file(s) were NOT applied:[/bold red]"
        )
        for rf in rejected_files:
            console.print(f"  [red]• {rf}[/red]")
        console.print(
            "[yellow]Hint: update the runbook step(s) above to use "
            "<<<SEARCH\n<exact lines>\n===\n<replacement>\n>>> blocks "
            "instead of full-file output, then re-run `agent implement`.[/yellow]"
        )
        logging.warning(
            "implement_incomplete story=%s rejected_files=%r",
            story_id, rejected_files,
        )

    # 1.3 AUTOMATION: Post-Apply Governance Gates
    if apply and implementation_success:
        console.print("\n[bold blue]🔒 Running Post-Apply Governance Gates...[/bold blue]")
        gate_results: list[gates.GateResult] = []
        modified_paths = [
            Path(block['file'])
            for block in parse_code_blocks(full_content)
            if block.get('file')
        ]

        # Gate 1: Security Scan
        if skip_security:
            gates.log_skip_audit("Security scan", story_id)
            console.print(f"⚠️  [AUDIT] Security gate skipped at {datetime.now().isoformat()}")
        else:
            sec_result = gates.run_security_scan(
                modified_paths,
                config.etc_dir / "security_patterns.yaml",
            )
            gate_results.append(sec_result)
            status = "PASSED" if sec_result.passed else "BLOCKED"
            color = "green" if sec_result.passed else "red"
            console.print(
                f"  [{color}][PHASE] {sec_result.name} ... {status}"
                f" ({sec_result.elapsed_seconds:.2f}s)[/{color}]"
            )
            if sec_result.details:
                console.print(f"    [dim]{sec_result.details}[/dim]")

        # Gate 2: QA Validation
        if skip_tests:
            gates.log_skip_audit("QA tests", story_id)
            console.print(f"⚠️  [AUDIT] Tests skipped at {datetime.now().isoformat()}")
        else:
            import yaml as _yaml
            try:
                agent_cfg = _yaml.safe_load(
                    (config.etc_dir / "agent.yaml").read_text()
                )
                _agent_sec = agent_cfg.get("agent", {})
                # Prefer test_commands (dict, polyglot) over test_command (str, legacy)
                test_cmd: "str | dict" = (
                    _agent_sec.get("test_commands")
                    or _agent_sec.get("test_command")
                    or "pytest"
                )
            except Exception:
                test_cmd = "pytest"
            # Safety: run_modified_files may not be set if the full-context
            # path processed all steps in bulk (no per-step accumulation).
            if 'run_modified_files' not in dir():
                run_modified_files = []
            qa_result = gates.run_qa_gate(test_cmd, modified_files=run_modified_files)
            gate_results.append(qa_result)
            status = "PASSED" if qa_result.passed else "BLOCKED"
            color = "green" if qa_result.passed else "red"
            console.print(
                f"  [{color}][PHASE] {qa_result.name} ... {status}"
                f" ({qa_result.elapsed_seconds:.2f}s)[/{color}]"
            )
            if not qa_result.passed and qa_result.details:
                console.print(f"    [dim]{qa_result.details}[/dim]")

        # Gate 3: Documentation Check
        docs_result = gates.run_docs_check(modified_paths)
        gate_results.append(docs_result)
        status = "PASSED" if docs_result.passed else "BLOCKED"
        color = "green" if docs_result.passed else "red"
        console.print(
            f"  [{color}][PHASE] {docs_result.name} ... {status}"
            f" ({docs_result.elapsed_seconds:.2f}s)[/{color}]"
        )
        if docs_result.details:
            console.print(f"    [dim]{docs_result.details}[/dim]")

        # Gate 4: PR Size Check (INFRA-092)
        pr_size_result = gates.check_pr_size(
            commit_message=story_title if story_title else None,
        )
        gate_results.append(pr_size_result)
        status = "PASSED" if pr_size_result.passed else "BLOCKED"
        color = "green" if pr_size_result.passed else "red"
        console.print(
            f"  [{color}][PHASE] {pr_size_result.name} ... {status}"
            f" ({pr_size_result.elapsed_seconds:.2f}s)[/{color}]"
        )
        if pr_size_result.details:
            console.print(f"    [dim]{pr_size_result.details}[/dim]")

        # Structured Verdict
        all_passed = all(r.passed for r in gate_results)
        if all_passed:
            console.print("\n[bold green]✅ All governance gates passed.[/bold green]")

            # Auto-stage modified files for commit pipeline
            files_to_stage = [str(p.resolve().relative_to(config.repo_root.resolve())) for p in modified_paths if p.exists()]
            
            # --- Update Linked Journeys ---
            if journey_result and journey_result.get("passed") and journey_result.get("journey_ids"):
                console.print("[dim]Updating linked journey(s) implementation stanzas...[/dim]")
                import yaml as _yaml
                
                new_impl_files = [f for f in files_to_stage if "/tests/" not in f and not f.startswith("tests/")]
                new_impl_tests = [f for f in files_to_stage if "/tests/" in f or f.startswith("tests/")]
                
                updated_journeys = []
                for jid in journey_result["journey_ids"]:
                    # Find journey file in config.journeys_dir
                    found_jfile = None
                    if config.journeys_dir.exists():
                        for jf in config.journeys_dir.rglob(f"{jid}*.yaml"):
                            if jf.name.startswith(jid):
                                found_jfile = jf
                                break
                    
                    if found_jfile:
                        try:
                            # Parse YAML carefully to preserve structure
                            j_data = _yaml.safe_load(found_jfile.read_text(errors="ignore"))
                            if isinstance(j_data, dict):
                                if "implementation" not in j_data:
                                    j_data["implementation"] = {}
                                
                                # Auto-extend existing arrays ensuring uniqueness
                                existing_files = set(j_data["implementation"].get("files") or [])
                                existing_tests = set(j_data["implementation"].get("tests") or [])
                                
                                existing_files.update(new_impl_files)
                                existing_tests.update(new_impl_tests)
                                
                                j_data["implementation"]["files"] = sorted(list(existing_files))
                                j_data["implementation"]["tests"] = sorted(list(existing_tests))
                                
                                # Write back
                                found_jfile.write_text(_yaml.dump(j_data, default_flow_style=False, sort_keys=False))
                                updated_journeys.append(found_jfile)
                        except Exception as e:
                            logger.warning(f"Failed to update journey YAML {found_jfile.name}: {e}")
                
                if updated_journeys:
                    console.print(f"[bold blue]📝 Updated {len(updated_journeys)} journey(s) with new implementation tracking.[/bold blue]")
                    for uj in updated_journeys:
                        files_to_stage.append(str(uj.resolve().relative_to(config.repo_root.resolve())))

            # Also stage story and runbook updates
            story_file_path = find_story_file(story_id) if story_id else None
            if story_file_path and story_file_path.exists():
                files_to_stage.append(str(story_file_path.resolve().relative_to(config.repo_root.resolve())))
            if runbook_file and runbook_file.exists():
                files_to_stage.append(str(runbook_file.resolve().relative_to(config.repo_root.resolve())))
            if files_to_stage:
                try:
                    subprocess.run(
                        ["git", "add"] + files_to_stage,
                        check=True,
                        capture_output=True,
                    )
                    console.print(f"[bold blue]📦 Staged {len(files_to_stage)} file(s) for commit.[/bold blue]")
                except subprocess.CalledProcessError as exc:
                    console.print(f"[yellow]⚠️  Auto-stage failed: {exc}[/yellow]")

            console.print("[bold green]✅ Implementation Complete (Local).[/bold green]")
            console.print(f"[dim]Story {story_id} remains 'In Progress'. Run 'agent preflight' then 'agent commit'.[/dim]")
        else:
            blocked = [r for r in gate_results if not r.passed]
            console.print(f"\n[bold red]❌ {len(blocked)} governance gate(s) BLOCKED.[/bold red]")
            for r in blocked:
                console.print(f"  [red]• {r.name}: {r.details}[/red]")
            console.print("[dim]Fix the issues above and re-run.[/dim]")



