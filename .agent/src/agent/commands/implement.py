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

"""CLI facade for the implement command (INFRA-102).

Parses Typer arguments and delegates all implementation logic to
:mod:`agent.core.implement`. This module intentionally contains no
application logic — it is a thin shim between the CLI surface and the core.
"""

import logging
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown


from agent.core.context import context_loader
from agent.core.config import config
from agent.core import utils as agent_utils
from agent.core.utils import find_runbook_file, get_next_id, scrub_sensitive_data
from agent.commands import gates
from agent.commands.utils import update_story_state

# ---------------------------------------------------------------------------
# Re-export core symbols so existing tests (import from agent.commands.implement)
# continue to work without modification (AC-5).
# ---------------------------------------------------------------------------
from agent.core.implement.circuit_breaker import (  # noqa: F401
    CircuitBreaker,
    count_edit_distance,
    MAX_EDIT_DISTANCE_PER_STEP,
    LOC_WARNING_THRESHOLD,
    LOC_CIRCUIT_BREAKER_THRESHOLD,
)
# Import core implementations for delegation
import agent.core.implement.circuit_breaker as _cb
from agent.core.implement.guards import (  # noqa: F401
    FILE_SIZE_GUARD_THRESHOLD,
    FileSizeGuardViolation,
    SOURCE_CONTEXT_HEAD_TAIL,
    SOURCE_CONTEXT_MAX_LOC,
    apply_change_to_file,
    apply_search_replace_to_file,
    backup_file,
    enforce_docstrings,
    validate_code_block,
)
from agent.core.implement.orchestrator import (  # noqa: F401
    Orchestrator,
    build_source_context,
)
from agent.core.implement.parser import (  # noqa: F401
    detect_malformed_modify_blocks,
    extract_approved_files,
    extract_cross_cutting_files,
    extract_modify_files,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
    validate_runbook_schema,
)
from agent.core.implement.resolver import (  # noqa: F401
    extract_story_id,
    resolve_path,
    _find_directories_in_repo as find_directories_in_repo,
    _find_file_in_repo as find_file_in_repo,
)

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

app = typer.Typer()
console = Console()


# ---------------------------------------------------------------------------
# Local wrappers for circuit-breaker functions.
#
# Tests patch agent.commands.implement.config / get_next_id / subprocess.run.
# Wrappers defined here ensure those patches intercept the actual calls (i.e.
# the functions read config/get_next_id/subprocess from THIS module's namespace
# at call time rather than from circuit_breaker.py's frozen closure).
# ---------------------------------------------------------------------------

def _micro_commit_step(
    story_id: str,
    step_index: int,
    step_loc: int,
    cumulative_loc: int,
    modified_files: List[str],
) -> bool:
    """Stage and commit modified files as a micro-save-point.

    Args:
        story_id: Story identifier for the commit message.
        step_index: 1-based step number.
        step_loc: Lines changed this step.
        cumulative_loc: Total lines changed so far.
        modified_files: Repo-relative paths modified this step.

    Returns:
        True on success, False if commit fails (non-fatal).
    """
    if not modified_files:
        return True
    try:
        subprocess.run(
            ["git", "add", "--"] + modified_files,
            check=True, capture_output=True, timeout=30,
        )
        msg = (
            f"feat({story_id}): implement step {step_index} "
            f"[{step_loc} LOC, {cumulative_loc} cumulative]"
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            check=True, capture_output=True, timeout=30,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _create_follow_up_story(
    original_story_id: str,
    original_title: str,
    remaining_chunks: List[str],
    completed_step_count: int,
    cumulative_loc: int,
) -> Optional[str]:
    """Create a follow-up story when the circuit breaker activates.

    Args:
        original_story_id: Story that triggered the circuit breaker.
        original_title: Human-readable title.
        remaining_chunks: Unprocessed runbook chunks.
        completed_step_count: Steps already completed.
        cumulative_loc: LOC at circuit breaker activation.

    Returns:
        New story ID if created, None on collision or failure.
    """
    from agent.core.implement.circuit_breaker import sanitize_branch_name
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

Circuit breaker activated during implementation of {original_story_id} at {cumulative_loc} LOC.
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

Revert changes from this follow-up story. Partial work from {original_story_id} remains intact.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
    safe_title = sanitize_branch_name(f"{original_title}-continuation")
    filename = f"{new_story_id}-{safe_title}.md"
    file_path = scope_dir / filename
    if file_path.exists():
        return None
    try:
        file_path.write_text(content)
        return new_story_id
    except Exception:
        return None


def _update_or_create_plan(
    original_story_id: str,
    follow_up_story_id: str,
    original_title: str,
) -> None:
    """Link original and follow-up stories in a Plan document.

    Args:
        original_story_id: The triggering story ID.
        follow_up_story_id: The newly created follow-up story ID.
        original_title: Human-readable story title.
    """
    prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
    plans_scope_dir = config.plans_dir / prefix
    plans_scope_dir.mkdir(parents=True, exist_ok=True)
    existing_plan = None
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
            logging.warning("Failed to update plan %s: %s", existing_plan, exc)
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



def get_current_branch() -> str:
    """Return the current git branch name, or empty string on failure."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return ""


def is_git_dirty() -> bool:
    """Return True when there are uncommitted (tracked) changes in the working tree."""
    try:
        return bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except Exception:
        return True


def sanitize_branch_name(title: str) -> str:
    """Convert a story title to a valid git branch name component."""
    name = title.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


def create_branch(story_id: str, title: str, yes: bool = False) -> None:
    """Create (or check out an existing) story branch.

    Handles dirty working trees by auto-stashing before checkout
    and popping afterwards. When the branch already exists, prompts
    the user to reuse it or delete and recreate it (unless ``yes``
    is set, in which case it reuses automatically).

    Args:
        story_id: Story ID used as the branch prefix.
        title: Raw story title; will be sanitized for use in the branch name.
        yes: Skip interactive prompts (auto-reuse existing branch).
    """
    safe_title = sanitize_branch_name(title)
    branch_name = f"{story_id}/{safe_title}"

    # Check whether the branch already exists (local)
    branch_exists = False
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            check=True, capture_output=True,
        )
        branch_exists = True
    except subprocess.CalledProcessError:
        pass

    # If branch exists, ask the user what to do
    if branch_exists:
        console.print(f"[yellow]⚠️  Branch '{branch_name}' already exists.[/yellow]")
        if yes:
            console.print("[dim]--yes flag set — deleting and recreating branch.[/dim]")
            reuse = False
        else:
            reuse = typer.confirm(
                "Reuse this branch? (No = delete and recreate from current HEAD)",
                default=True,
            )
        if not reuse:
            try:
                subprocess.run(
                    ["git", "branch", "-D", branch_name],
                    check=True, capture_output=True,
                )
                console.print(f"[dim]Deleted branch '{branch_name}'.[/dim]")
                branch_exists = False
            except subprocess.CalledProcessError as exc:
                stderr_msg = exc.stderr.decode().strip() if exc.stderr else str(exc)
                console.print(
                    f"[bold red]❌ Failed to delete branch '{branch_name}': "
                    f"{stderr_msg}[/bold red]"
                )
                raise typer.Exit(code=1)

    # Stash any dirty state (including untracked files) before switching
    stashed = False
    try:
        result = subprocess.run(
            ["git", "stash", "push", "--include-untracked", "-m", f"auto-stash for {branch_name}"],
            capture_output=True, text=True, timeout=30,
        )
        # git stash returns 0 even when there's nothing to stash;
        # check output to know if it actually stashed anything
        stashed = result.returncode == 0 and "No local changes" not in result.stdout
    except subprocess.CalledProcessError:
        pass

    try:
        if branch_exists:
            subprocess.run(
                ["git", "checkout", branch_name],
                check=True, capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                check=True, capture_output=True,
            )
    except subprocess.CalledProcessError as exc:
        # Pop the stash before raising so we don't lose work
        if stashed:
            subprocess.run(["git", "stash", "pop"], capture_output=True)
        stderr_msg = exc.stderr.decode().strip() if exc.stderr else str(exc)
        console.print(
            f"[bold red]❌ Failed to {'checkout' if branch_exists else 'create'} "
            f"branch '{branch_name}': {stderr_msg}[/bold red]"
        )
        raise typer.Exit(code=1)

    # Restore stashed changes on the new branch
    if stashed:
        pop_result = subprocess.run(
            ["git", "stash", "pop"], capture_output=True, text=True,
        )
        if pop_result.returncode != 0:
            console.print(
                "[yellow]⚠️  Auto-stash pop had conflicts. "
                "Run 'git stash pop' manually to resolve.[/yellow]"
            )

# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

@app.command()
def implement(
    story_id: str = typer.Argument(..., help="Story ID (e.g. INFRA-042)"),
    apply: bool = typer.Option(False, "--apply", help="Write changes to disk"),
    stage: bool = typer.Option(False, "--stage", help="Stage modified files (git add) after successful apply"),
    commit: bool = typer.Option(False, "--commit", help="Auto-commit each step after applying (implies --stage)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip QA gate (audit-logged)"),
    skip_security: bool = typer.Option(False, "--skip-security", help="Skip security scan (audit-logged)"),
    legacy_apply: bool = typer.Option(False, "--legacy-apply", help="Bypass safe-apply size guard"),
    model: Optional[str] = typer.Option(None, "--model", help="Override AI model"),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force specific AI provider"),
    thorough: bool = typer.Option(True, "--thorough", help="Use thorough governance context (Default: True)"),
    quick: bool = typer.Option(False, "--quick", help="Opt out of thorough mode for fast/cheap runs"),
    allow_dirty: bool = typer.Option(False, "--allow-dirty", help="Allow running with uncommitted changes"),
) -> None:
    """Implement a story from its accepted runbook.

    if quick:
        thorough = False

    Finds the runbook for STORY_ID, detects whether it contains verbatim
    code blocks (applied directly, no AI), or delegates to the AI for
    open-ended steps. Runs governance gates after applying changes.
    """
    console.print(f"\n[bold blue]🚀 Implementing Runbook {story_id}...[/bold blue]\n")

    # ------------------------------------------------------------------
    # 0. Git hygiene guards (tested by test_implement_branching.py)
    # ------------------------------------------------------------------
    if not allow_dirty and is_git_dirty():
        console.print(
            "[bold red]❌ Uncommitted changes detected. "
            "Commit or stash before implementing, or use --allow-dirty.[/bold red]"
        )
        raise typer.Exit(code=1)

    current_branch = get_current_branch()
    expected_branch_prefix = story_id + "/"
    on_correct_branch = (
        current_branch == "main"
        or current_branch == "master"
        or current_branch.startswith(expected_branch_prefix)
    )
    if not on_correct_branch:
        console.print(
            f"[bold red]❌ You must be on 'main' or a '{story_id}/...' "
            f"branch to implement. Currently on '{current_branch}'.[/bold red]"
        )
        raise typer.Exit(code=1)

    runbook_path = find_runbook_file(story_id)
    if not runbook_path:
        console.print(f"[bold red]❌ Runbook file not found for {story_id}.[/bold red]")
        console.print("[dim]Run `agent new-runbook` to create one.[/dim]")
        raise typer.Exit(code=1)

    runbook_content = runbook_path.read_text()

    # State guard: only ACCEPTED runbooks may be implemented
    state_check = re.search(r"^##\s*State\s+(\w+)", runbook_content, re.MULTILINE)
    if state_check:
        state = state_check.group(1).strip().upper()
        if state != "ACCEPTED":
            console.print(
                f"[bold red]❌ Runbook state '{state}' is not ACCEPTED. "
                f"Only ACCEPTED runbooks can be implemented.[/bold red]"
            )
            raise typer.Exit(code=1)

    runbook_content_scrubbed = scrub_sensitive_data(runbook_content)

    # ------------------------------------------------------------------
    # 2. Locate story metadata using story ID extracted from runbook
    # ------------------------------------------------------------------
    # extract_story_id is used (and patchable) to resolve which story file to find.
    story_ref_id = extract_story_id(runbook_content_scrubbed) or story_id
    story_title = story_id
    story_path = agent_utils.find_story_file(story_ref_id)  # goes via module; patches intercept
    story_content = ""
    linked_journey_ids: List[str] = []
    if not story_path:
        # Fallback: glob the stories dir directly
        stories_base = config.stories_dir or Path(".agent/cache/stories")
        for sf in stories_base.rglob(f"{story_ref_id}*.md"):
            story_path = sf
            break
    if story_path and story_path.exists():
        story_content = story_path.read_text()
        title_match = re.search(r"^# .*?:\s*(.+)$", story_content, re.MULTILINE)
        if title_match:
            story_title = title_match.group(1).strip()
        # Extract Linked Journeys
        jrn_match = re.search(
            r"## Linked Journeys\s+(.+?)(?=##|$)", story_content, re.DOTALL
        )
        if jrn_match:
            linked_journey_ids = re.findall(r"JRN-(\d+)", jrn_match.group(1))

    # Journey Gate: fire only when Linked Journeys section exists but has no
    # real JRN-NNN IDs (e.g. only the placeholder JRN-XXX).
    has_linked_journeys_section = story_content and "## Linked Journeys" in story_content
    if has_linked_journeys_section and not linked_journey_ids:
        console.print(
            "[bold red]🚨 Journey Gate FAILED: story has no linked Journeys "
            "(add at least one JRN-NNN entry).[/bold red]"
        )
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # 3. Pre-flight branch hygiene
    # ------------------------------------------------------------------
    if current_branch in ("main", "master"):
        create_branch(story_id, story_title, yes=yes)
        console.print(f"[green]✅ Branch created: {story_id}/{sanitize_branch_name(story_title)}[/green]")
    else:
        console.print(f"[green]Already on valid story branch: {current_branch}[/green]")

    # ------------------------------------------------------------------
    # 4. Load governance context
    # ------------------------------------------------------------------
    import asyncio
    ctx = asyncio.run(context_loader.load_context())
    rules_content = ctx.get("rules", "")
    instructions_content = ctx.get("instructions", "")
    adrs_content = ctx.get("adrs", "")

    guide_path = config.agent_dir / "workflows/implement.md"
    guide_content = scrub_sensitive_data(guide_path.read_text()) if guide_path.exists() else ""

    rules_content = re.sub(r"<!--.*?-->", "", rules_content, flags=re.DOTALL)
    rules_content = re.sub(r"\n{3,}", "\n\n", rules_content)

    app_license_template = config.get_app_license_header()
    license_instruction = ""
    if app_license_template:
        license_instruction = (
            f"\n- **CRITICAL**: All new source code files MUST begin with "
            f"the following exact license header:\n{app_license_template}\n"
        )

    # ------------------------------------------------------------------
    # 7. Schema validation — hard block before any file is touched.
    #    A malformed runbook causes partial-apply failures that leave the
    #    working tree in an inconsistent state. Fail fast with a full
    #    violation list so the developer can fix the runbook first.
    # ------------------------------------------------------------------
    schema_violations = validate_runbook_schema(runbook_content_scrubbed)
    if schema_violations:
        console.print(
            f"\n[bold red]❌ RUNBOOK SCHEMA INVALID "
            f"— {len(schema_violations)} violation(s) found:[/bold red]"
        )
        for v in schema_violations:
            console.print(f"  [red]• {v}[/red]")
        console.print(
            "\n[yellow]Fix the runbook then re-run 'agent implement'. "
            "No files have been modified.[/yellow]"
        )
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # 8. Verbatim-first: if the runbook contains explicit code blocks,
    #    apply them directly — no AI call, no token cost.
    # ------------------------------------------------------------------
    _all_sr = parse_search_replace_blocks(runbook_content_scrubbed)
    _all_code = parse_code_blocks(runbook_content_scrubbed)

    full_content = ""
    implementation_success = False
    rejected_files: List[str] = []
    run_modified_files: List[str] = []
    cumulative_loc = 0

    if _all_sr or _all_code:
        console.print(
            f"[bold green]⚡ Verbatim runbook: "
            f"{len(_all_sr)} S/R + {len(_all_code)} full-file blocks "
            f"— applying directly, no AI needed[/bold green]"
        )
        implementation_success = True

        if apply:
            # ---- Pre-processing: Build S/R index and detect NEW+MODIFY ----
            _sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for _b in _all_sr:
                _sr_by_file[_b["file"]].append(_b)
            _new_files = {_b["file"] for _b in _all_code if not Path(_b["file"]).exists()}

            # ---- Phase 1: Create NEW files first ----
            # If a NEW file also has S/R MODIFY blocks, pre-apply the S/R
            # edits to the content in-memory before writing.  This handles
            # the common case where the AI generates both [NEW] and [MODIFY]
            # blocks for the same file across different steps.
            _new_created: set = set()
            for _b in _all_code:
                if Path(_b["file"]).exists():
                    continue  # existing file — handled in Phase 3
                _content = _b["content"]

                # Pre-merge any S/R blocks targeting this NEW file
                if _b["file"] in _sr_by_file:
                    _merge_ok = True
                    for _sr in _sr_by_file[_b["file"]]:
                        if _sr["search"] in _content:
                            _content = _content.replace(_sr["search"], _sr["replace"], 1)
                        else:
                            console.print(
                                f"[yellow]⚠ Pre-merge S/R skipped for {_b['file']}: "
                                f"search text not found in [NEW] content[/yellow]"
                            )
                            _merge_ok = False
                    if _merge_ok:
                        console.print(
                            f"[cyan]🔀 Pre-merged {len(_sr_by_file[_b['file']])} S/R block(s) "
                            f"into [NEW] {_b['file']}[/cyan]"
                        )

                # Auto-fix missing module docstrings for NEW files.
                # Test files are explicitly exempt — test functions intentionally
                # lack docstrings and this is standard pytest convention.
                _is_test_file = (
                    Path(_b["file"]).name.startswith("test_")
                    or Path(_b["file"]).name.endswith("_test.py")
                    or "/tests/" in _b["file"].replace("\\", "/")
                )
                _vres = enforce_docstrings(_b["file"], _content) if not _is_test_file else None
                if _vres and not _vres.passed:
                    # Try auto-fixing: add a module docstring
                    _mod_name = Path(_b["file"]).stem
                    _docstring = f'"""{_mod_name} module."""\n\n'
                    _content = _docstring + _content
                    console.print(
                        f"[yellow]🔧 Auto-added module docstring for {_b['file']}[/yellow]"
                    )
                    # Re-validate after fix — downgrade remaining violations to
                    # warnings so the file is still written.  Hard-blocking here
                    # silently drops [NEW] files that have minor function-level
                    # docstring gaps (e.g. token_counter.__init__), which is the
                    # root cause of the INCOMPLETE IMPLEMENTATION false-positives.
                    # Preflight will surface any remaining gaps after apply.
                    _vres = enforce_docstrings(_b["file"], _content)
                    if not _vres.passed:
                        console.print(
                            f"[yellow]⚠ DOCSTRING WARN: {_b['file']} "
                            f"({len(_vres.errors)} gap(s) — file will be written, fix before preflight)[/yellow]"
                        )
                        for _v in _vres.errors:
                            console.print(f"   [yellow]• {_v}[/yellow]")
                if _vres and _vres.warnings:
                    for _w in _vres.warnings:
                        console.print(f"   [yellow]⚠ {_w}[/yellow]")
                try:
                    _ok = apply_change_to_file(_b["file"], _content, yes, legacy_apply=legacy_apply)
                except FileSizeGuardViolation as exc:
                    console.print(
                        f"[bold yellow]⚠ SKIPPED (size guard): {_b['file']}[/bold yellow]\n"
                        f"   [dim]{exc}[/dim]"
                    )
                    rejected_files.append(_b["file"])
                    continue
                if _ok:
                    run_modified_files.append(_b["file"])
                    _new_created.add(_b["file"])
                else:
                    rejected_files.append(_b["file"])

            # ---- Phase 2: Apply S/R (MODIFY) blocks ----
            # Skip files already handled by Phase 1 pre-merge.
            if _all_sr:
                for _fp, _blocks in _sr_by_file.items():
                    if _fp in _new_created:
                        continue  # already pre-merged in Phase 1
                    _orig = Path(_fp).read_text() if Path(_fp).exists() else ""
                    _ok, _final = apply_search_replace_to_file(_fp, _blocks, yes)
                    if _ok:
                        cumulative_loc += count_edit_distance(_orig, _final)
                        run_modified_files.append(_fp)
                    else:
                        rejected_files.append(_fp)

            # ---- Phase 3: Replace existing files (full-content blocks) ----
            # Skip files already handled by S/R or created in Phase 1.
            _sr_done = {_b["file"] for _b in _all_sr}
            for _b in _all_code:
                if _b["file"] in _sr_done or _b["file"] in _new_created:
                    continue
                if not Path(_b["file"]).exists():
                    continue  # shouldn't happen, but guard
                _content = _b["content"]
                _is_test_file = (
                    Path(_b["file"]).name.startswith("test_")
                    or Path(_b["file"]).name.endswith("_test.py")
                    or "/tests/" in _b["file"].replace("\\", "/")
                )
                _vres = enforce_docstrings(_b["file"], _content) if not _is_test_file else None
                if _vres and not _vres.passed:
                    # Auto-fix: add module docstring
                    _mod_name = Path(_b["file"]).stem
                    _docstring = f'"""{_mod_name} module."""\n\n'
                    _content = _docstring + _content
                    console.print(
                        f"[yellow]🔧 Auto-added module docstring for {_b['file']}[/yellow]"
                    )
                    _vres = enforce_docstrings(_b["file"], _content)
                    if not _vres.passed:
                        console.print(
                            f"[yellow]⚠ DOCSTRING WARN: {_b['file']} "
                            f"({len(_vres.errors)} gap(s) — file will be written, fix before preflight)[/yellow]"
                        )
                        for _v in _vres.errors:
                            console.print(f"   [yellow]• {_v}[/yellow]")
                if _vres and _vres.warnings:
                    for _w in _vres.warnings:
                        console.print(f"   [yellow]⚠ {_w}[/yellow]")
                _orig = Path(_b["file"]).read_text()
                try:
                    _ok = apply_change_to_file(_b["file"], _content, yes, legacy_apply=legacy_apply)
                except FileSizeGuardViolation as exc:
                    console.print(
                        f"[bold yellow]⚠ SKIPPED (size guard): {_b['file']}[/bold yellow]\n"
                        f"   [dim]{exc}[/dim]"
                    )
                    rejected_files.append(_b["file"])
                    continue
                if _ok:
                    cumulative_loc += count_edit_distance(_orig, _content)
                    run_modified_files.append(_b["file"])
                else:
                    rejected_files.append(_b["file"])

            full_content = f"[verbatim: {len(run_modified_files)} file(s) applied]"
            if commit:
                _micro_commit_step(story_id, 1, cumulative_loc, cumulative_loc, run_modified_files)
            console.print(f"[green]✅ Verbatim apply complete ({cumulative_loc} LOC)[/green]")
        else:
            files_targeted = sorted(list({b["file"] for b in _all_sr} | {b["file"] for b in _all_code}))
            if files_targeted:
                files_list = "\n".join(f"- `{f}`" for f in files_targeted)
                out_parts = [f"**Targeted Files:**\n{files_list}\n"]
                for b in _all_code:
                    out_parts.append(f"**File: {b['file']}**\n```python\n{b['content']}\n```")
                for b in _all_sr:
                    search = b.get("search", "")
                    replace = b.get("replace", "")
                    out_parts.append(f"**File: {b['file']}**\n```text\n<<<SEARCH\n{search}\n===\n{replace}\n>>>\n```")
                full_content = "\n\n".join(out_parts)
            else:
                full_content = ""

    # ------------------------------------------------------------------
    # 8. AI path: full-context attempt, then chunked fallback
    # ------------------------------------------------------------------
    if not implementation_success:
        from agent.core.ai import ai_service

        # Set provider before AI calls so it applies to both full-context and chunks
        if provider:
            ai_service.set_provider(provider)

        console.print("[dim]Attempting full context execution...[/dim]")

        modify_files = extract_modify_files(runbook_content_scrubbed)
        source_context = build_source_context(modify_files) if modify_files else ""
        if source_context:
            console.print(
                f"[dim]📄 Source context: {len(modify_files)} file(s) "
                f"({len(source_context)} chars)[/dim]"
            )

        system_prompt = f"""You are an Implementation Agent.
Your goal is to EXECUTE ALL tasks defined in the provided RUNBOOK.

INSTRUCTIONS:
- Use REPO-RELATIVE paths (e.g. .agent/src/agent/main.py). Never use 'agent/' as root.
- For EXISTING files emit search/replace blocks:

File: path/to/file.py
<<<SEARCH
exact lines
===
replacement
>>>

- For NEW files emit complete content:

File: path/to/new_file.py
```python
# content
```

- NEVER emit full-file content for files listed in SOURCE CONTEXT — use search/replace.
- Every module, class, and function MUST have a PEP-257 docstring.{license_instruction}
"""
        user_prompt = f"""RUNBOOK:
{runbook_content_scrubbed}

SOURCE CONTEXT:
{source_context}

RULES:
{rules_content}

INSTRUCTIONS:
{instructions_content}

ADRs:
{adrs_content}
"""
        fallback_needed = False
        try:
            console.print("[bold green]🤖 AI coding (Full Context)...[/bold green]")
            with console.status("[bold green]🤖 Working...[/bold green]") as status:
                full_content = ai_service.complete(system_prompt, user_prompt, model=model, rich_status=status)
            if not full_content:
                raise ValueError("Empty AI response")
            implementation_success = True
        except Exception as exc:
            console.print(f"[yellow]⚠️  Full context failed: {exc}[/yellow]")
            console.print("[bold blue]🔄 Falling back to chunked processing...[/bold blue]")
            fallback_needed = True

        if fallback_needed:
            from agent.core.utils import load_governance_context
            filtered_rules = scrub_sensitive_data(load_governance_context(coding_only=True))
            filtered_rules = re.sub(r"<!--.*?-->", "", filtered_rules, flags=re.DOTALL)
            filtered_rules = re.sub(r"\n{3,}", "\n\n", filtered_rules)

            global_ctx, chunks = split_runbook_into_chunks(runbook_content_scrubbed)
            console.print(f"[dim]Runbook split into {len(chunks)} tasks[/dim]")

            if provider:
                ai_service.set_provider(provider)
            else:
                ai_service.reset_provider()

            completed_steps = 0
            _approved = extract_approved_files(runbook_content)
            _cross_cutting = extract_cross_cutting_files(runbook_content)
            orchestrator = Orchestrator(
                story_id, yes=yes, legacy_apply=legacy_apply,
                approved_files=_approved, cross_cutting_files=_cross_cutting,
            )

            # INFRA-169: Parallel path when all chunks are verbatim
            if orchestrator.use_concurrency and apply:
                all_verbatim = all(
                    parse_search_replace_blocks(c) or parse_code_blocks(c)
                    for c in chunks
                )
                if all_verbatim:
                    console.print(
                        f"[bold cyan]⚡ Concurrent mode: applying {len(chunks)} "
                        f"verbatim chunks in parallel[/bold cyan]"
                    )
                    results = asyncio.run(orchestrator.apply_chunks_parallel(chunks))
                    for idx, (step_loc, step_files) in enumerate(results):
                        cumulative_loc += step_loc
                        run_modified_files.extend(step_files)
                        completed_steps = idx + 1
                        if commit:
                            _micro_commit_step(
                                story_id, idx + 1, step_loc,
                                cumulative_loc, step_files,
                            )
                    console.print(
                        f"[green]✅ Parallel apply complete "
                        f"({cumulative_loc} LOC, {len(chunks)} chunks)[/green]"
                    )
                    rejected_files = orchestrator.rejected_files
                    orchestrator.print_incomplete_summary()
                    implementation_success = True
                    # Skip the serial loop below
                    fallback_needed = False
                    chunks = []

            # INFRA-169: Create a single event loop for all serial chunk
            # applications, avoiding the asyncio.run-per-chunk anti-pattern.
            _loop = asyncio.new_event_loop()

            for idx, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    console.print(
                        f"\n[bold blue]🚀 Task {idx+1}/{len(chunks)}...[/bold blue]"
                    )

                # Per-chunk verbatim short-circuit
                c_sr = parse_search_replace_blocks(chunk)
                c_code = parse_code_blocks(chunk)
                if c_sr or c_code:
                    console.print(
                        f"[dim]⚡ Step {idx+1}: verbatim ({len(c_sr)} S/R, "
                        f"{len(c_code)} full-file) — no AI[/dim]"
                    )
                    step_loc, step_files = _loop.run_until_complete(
                        orchestrator.apply_chunk(chunk, idx + 1)
                    )
                    full_content += f"\n[verbatim step {idx+1}]"
                    cumulative_loc += step_loc
                    completed_steps = idx + 1
                    run_modified_files.extend(step_files)
                    if commit:
                        _micro_commit_step(story_id, idx + 1, step_loc, cumulative_loc, step_files)
                    console.print(
                        f"[green]✅ Step {idx+1} ({step_loc} LOC, "
                        f"{cumulative_loc} cumulative)[/green]"
                    )
                    if cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD:
                        console.print(
                            f"[bold red]🛑 Circuit breaker: {cumulative_loc} LOC[/bold red]"
                        )
                        break
                    continue

                # AI-generated chunk
                chunk_modify = extract_modify_files(chunk)
                chunk_ctx = build_source_context(chunk_modify) if chunk_modify else ""

                chunk_system = f"""You are an Implementation Agent.
ONLY implement the CURRENT TASK below. Keep changes under {MAX_EDIT_DISTANCE_PER_STEP} lines.
Use search/replace for existing files, full-file for new files.
Every module/class/function MUST have a PEP-257 docstring.{license_instruction}
"""
                chunk_user = f"""GLOBAL CONTEXT:
{global_ctx[:8000]}

CURRENT TASK:
{chunk}

SOURCE CONTEXT:
{chunk_ctx}

RULES:
{filtered_rules}

INSTRUCTIONS:
{instructions_content}

ADRs:
{adrs_content}
"""
                try:
                    console.print(
                        f"[bold green]🤖 AI coding task {idx+1}/{len(chunks)}...[/bold green]"
                    )
                    with console.status("[bold green]🤖 Working...[/bold green]") as status:
                        chunk_result = ai_service.complete(
                            chunk_system, chunk_user, model=model, rich_status=status
                        )
                except Exception as exc:
                    console.print(f"[bold red]❌ Task {idx+1} failed: {exc}[/bold red]")
                    raise typer.Exit(code=1)

                if not chunk_result:
                    continue

                full_content += f"\n\n{chunk_result}"

                if apply:
                    step_loc, step_files = _loop.run_until_complete(
                        orchestrator.apply_chunk(chunk_result, idx + 1)
                    )
                    cumulative_loc += step_loc
                    completed_steps = idx + 1
                    run_modified_files.extend(step_files)
                    if commit:
                        _micro_commit_step(
                            story_id, idx + 1, step_loc, cumulative_loc, step_files
                        )
                    console.print(
                        f"[green]✅ Step {idx+1} committed "
                        f"({step_loc} LOC, {cumulative_loc} cumulative)[/green]"
                    )

                    if LOC_WARNING_THRESHOLD <= cumulative_loc < LOC_CIRCUIT_BREAKER_THRESHOLD:
                        console.print(
                            f"[bold yellow]⚠️  Approaching LOC limit: "
                            f"{cumulative_loc}/{LOC_CIRCUIT_BREAKER_THRESHOLD}[/bold yellow]"
                        )

                    if cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD:
                        remaining = chunks[idx + 1 :]
                        console.print(
                            f"\n[bold red]🛑 Circuit breaker at {cumulative_loc} LOC[/bold red]"
                        )
                        if remaining:
                            follow_up = _create_follow_up_story(
                                story_id, story_title, remaining, completed_steps, cumulative_loc
                            )
                            if follow_up:
                                console.print(
                                    f"[green]📋 Follow-up story created: {follow_up}[/green]"
                                )
                        break

            rejected_files = orchestrator.rejected_files
            orchestrator.print_incomplete_summary()
            implementation_success = True

        # Apply full-context AI output to disk (if not chunked)
        if implementation_success and apply and not fallback_needed and _all_sr == [] and _all_code == []:
            orchestrator_fc = Orchestrator(
                story_id, yes=yes, legacy_apply=legacy_apply,
                approved_files=_approved, cross_cutting_files=_cross_cutting,
            )
            step_loc, step_files = asyncio.run(orchestrator_fc.apply_chunk(full_content, 1))
            cumulative_loc += step_loc
            run_modified_files.extend(step_files)
            rejected_files = orchestrator_fc.rejected_files
            orchestrator_fc.print_incomplete_summary()
            if commit:
                _micro_commit_step(story_id, 1, step_loc, cumulative_loc, step_files)

    # ------------------------------------------------------------------
    # 9. Surface incomplete summary
    # ------------------------------------------------------------------
    if rejected_files:
        console.print(
            f"\n[bold red]🚨 INCOMPLETE IMPLEMENTATION "
            f"— {len(rejected_files)} file(s) NOT applied:[/bold red]"
        )
        for rf in rejected_files:
            console.print(f"  [red]• {rf}[/red]")
        console.print(
            "[yellow]Hint: use <<<SEARCH\\n<lines>\\n===\\n<replacement>\\n>>> "
            "blocks then re-run `agent implement`.[/yellow]"
        )
        logging.warning(
            "implement_incomplete story=%s rejected_files=%r",
            story_id, rejected_files,
        )
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # 9b. Stage modified files (if --stage or --commit)
    # ------------------------------------------------------------------
    if apply and implementation_success and run_modified_files and (stage or commit):
        try:
            subprocess.run(
                ["git", "add", "--"] + run_modified_files,
                check=True, capture_output=True, timeout=30,
            )
            console.print(
                f"[green]📦 Staged {len(run_modified_files)} file(s) for commit.[/green]"
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]⚠️  Failed to stage files: {e}[/yellow]")

    # ------------------------------------------------------------------
    # 10. Post-apply governance gates
    # ------------------------------------------------------------------
    if apply and implementation_success:
        console.print("\n[bold blue]🔒 Running Post-Apply Governance Gates...[/bold blue]")
        gate_results = []

        modified_paths = [Path(f) for f in run_modified_files if f]

        if skip_security:
            gates.log_skip_audit("Security scan", story_id)
            console.print(f"⚠️  [AUDIT] Security gate skipped at {datetime.now().isoformat()}")
        else:
            sec = gates.run_security_scan(
                modified_paths,
                config.etc_dir / "security_patterns.yaml",
            )
            gate_results.append(sec)
            _print_gate(sec)

        import yaml as _yaml
        try:
            agent_cfg = _yaml.safe_load((config.etc_dir / "agent.yaml").read_text())
            test_cmd = (
                agent_cfg.get("agent", {}).get("test_commands")
                or agent_cfg.get("agent", {}).get("test_command")
                or "pytest"
            )
        except Exception:
            test_cmd = "pytest"

        if skip_tests:
            gates.log_skip_audit("QA tests", story_id)
            console.print(f"⚠️  [AUDIT] Tests skipped at {datetime.now().isoformat()}")
        else:
            qa = gates.run_qa_gate(test_cmd, modified_files=run_modified_files)
            gate_results.append(qa)
            _print_gate(qa)

        # INFRA-137: run_docs_check removed — enforced at source (INFRA-136).

        pr_size = gates.check_pr_size(commit_message=story_title)
        gate_results.append(pr_size)
        _print_gate(pr_size)

        # INFRA-170: Deterministic Complexity Gates (ADR-012)
        # Enforces file length (>500 LOC) and function length (21-50 WARN, >50 BLOCK)
        from agent.core.governance.complexity import get_complexity_report
        complexity_passed = True
        complexity_details = []
        for f in modified_paths:
            if f.suffix == ".py":
                try:
                    report = get_complexity_report(f.read_text(errors="ignore"), str(f))
                    if report.file_verdict != "PASS":
                        complexity_details.append(f"WARN: {f.name} is {report.total_loc} LOC (limit: 500)")
                    for fn in report.functions:
                        if fn.verdict == "BLOCK":
                            complexity_passed = False
                            complexity_details.append(f"BLOCK: {f.name} function '{fn.name}' is {fn.length} lines (limit: 50)")
                        elif fn.verdict == "WARN":
                            complexity_details.append(f"WARN: {f.name} function '{fn.name}' is {fn.length} lines (threshold: 20)")
                except Exception as e:
                    complexity_details.append(f"ERROR: Failed to analyze {f.name}: {e}")
        comp_gate = gates.GateResult(
            name="Complexity Standards",
            passed=complexity_passed,
            details="\n".join(complexity_details) if complexity_details else "All modified functions meet ADR-012 standards.",
            elapsed_seconds=0.1
        )
        gate_results.append(comp_gate)
        _print_gate(comp_gate)

        if linked_journey_ids:
            try:
                import yaml
                
                updated_journeys = []
                for jid in linked_journey_ids:
                    # Construct full formatted journey ID if it's just a number
                    full_jid = jid if jid.startswith("JRN-") else f"JRN-{jid}"
                    jf = None
                    if config.journeys_dir.exists():
                        for f in config.journeys_dir.rglob(f"{full_jid}*"):
                            if f.is_file() and f.suffix in (".yml", ".yaml"):
                                jf = f
                                break
                    if jf and jf.exists():
                        raw_text = jf.read_text(encoding="utf-8")
                        # Preserve the leading comment block (e.g. Apache 2.0
                        # license header) that yaml.safe_load silently discards.
                        comment_lines: list[str] = []
                        for _ln in raw_text.splitlines():
                            if _ln.startswith("#") or _ln.strip() == "":
                                comment_lines.append(_ln)
                            else:
                                break
                        jdata = yaml.safe_load(raw_text)
                        if jdata and "implementation" in jdata:
                            # Add modified files
                            cur_files = set(jdata["implementation"].get("files", []))
                            for mf in run_modified_files:
                                if not str(mf).startswith("tests"):
                                    cur_files.add(str(mf))
                            jdata["implementation"]["files"] = sorted(list(cur_files))

                            # Add modified tests
                            cur_tests = set(jdata["implementation"].get("tests", []))
                            for mf in run_modified_files:
                                if str(mf).startswith("tests"):
                                    cur_tests.add(str(mf))
                            jdata["implementation"]["tests"] = sorted(list(cur_tests))

                            dumped = yaml.safe_dump(jdata, sort_keys=False)
                            if comment_lines:
                                header = "\n".join(comment_lines) + "\n\n"
                                dumped = header + dumped
                            jf.write_text(dumped, encoding="utf-8")
                            updated_journeys.append(jf.name)
                if updated_journeys:
                    console.print(f"[dim]Updated linked journey(s): {', '.join(updated_journeys)}[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠️  Failed to update journey YAMLs: {e}[/yellow]")

        all_passed = all(r.passed for r in gate_results)
        if all_passed:
            console.print("\n[bold green]✅ All governance gates passed.[/bold green]")
            update_story_state(story_id, "COMMITTED", context_prefix="Phase 10")
        else:
            console.print(
                f"\n[bold yellow]⚠️  Some governance gates produced warnings.[/bold yellow]"
            )
            hint = (
                f"[yellow]Run [bold]agent preflight --story {story_id}[/bold] "
                f"to resolve issues before opening a PR.[/yellow]"
            )
            console.print(hint)
            update_story_state(story_id, "REVIEW_NEEDED", context_prefix="Phase 10")

    if not apply:
        console.print("\n[dim]Dry-run complete. Re-run with --apply to write changes.[/dim]")
        if full_content:
            console.print(Markdown(full_content[:4000]))


def _print_gate(result: "gates.GateResult") -> None:
    """Print a single gate result to the console.

    Passed gates are shown in green. Failed gates are shown in yellow —
    they are non-fatal warnings during ``implement``; ``preflight`` is
    the hard enforcement point before a PR is opened.
    """
    status = "PASSED" if result.passed else "WARN"
    color = "green" if result.passed else "yellow"
    icon = "✅" if result.passed else "⚠️ "
    console.print(
        f"  [{color}]{icon} [PHASE] {result.name} ... {status} "
        f"({result.elapsed_seconds:.2f}s)[/{color}]"
    )
    if result.details:
        console.print(f"    [dim]{result.details}[/dim]")
# nolint: loc-ceiling
