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

"""
Implementation of the agent decompose-story command.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, TypedDict

import typer
from rich.console import Console
from opentelemetry import trace

from agent.main import app
from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.utils import (
    find_story_file,
    get_full_license_header,
    get_next_id,
    sanitize_title,
    scrub_sensitive_data,
)
from agent.commands.utils import update_story_state


class _PlannedOperationRequired(TypedDict):
    """Required keys shared by every planned operation."""

    type: str
    """Operation kind — ``'STORY'`` or ``'PLAN'``."""
    path: Path
    """Absolute path of the file to be written."""
    id: str
    """Story or plan identifier (e.g. ``'INFRA-158'``)."""
    content: str
    """Full markdown content to write to *path*."""


class PlannedOperation(_PlannedOperationRequired, total=False):
    """A single file-creation operation planned by the decompose-story command.

    ``title`` is only present for ``type='STORY'`` operations; it holds the
    human-readable story description taken from the split-request suggestions.
    """

    title: str
    """Story title / description (only set when ``type == 'STORY'``)."""


class SplitRequest(TypedDict):
    """Schema for the split-request JSON files produced by ``agent new-runbook``."""

    suggestions: List[str]
    """One entry per desired child story (the story title or description)."""
    reason: str
    """Human-readable explanation of why the parent story is being split."""


def get_next_ids(prefix: str, count: int) -> List[str]:
    """Return *count* sequential, globally-unique story IDs for *prefix*.

    Calls :func:`agent.core.utils.get_next_id` once per requested ID,
    passing the accumulating list of just-allocated IDs as phantom files via
    a temporary overlay.  Because ``get_next_id`` scans the filesystem and
    the local DB, each successive call naturally returns the next integer.

    Args:
        prefix: Namespace prefix, e.g. ``'INFRA'``.
        count: Number of sequential IDs to allocate.

    Returns:
        List of *count* ID strings ordered from lowest to highest.
    """
    ids: List[str] = []
    for _ in range(count):
        next_id = get_next_id(config.stories_dir / prefix, prefix)
        # Create a placeholder so the next call increments past this one.
        placeholder = config.stories_dir / prefix / f"{next_id}-placeholder.md"
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        placeholder.touch()
        ids.append(next_id)
    # Remove placeholders — real files will be written by the caller.
    for next_id in ids:
        placeholder = config.stories_dir / prefix / f"{next_id}-placeholder.md"
        placeholder.unlink(missing_ok=True)
    return ids

console = Console()
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

@app.command(name="decompose-story")
def decompose_story(
    story_id: str = typer.Argument(..., help="The ID of the story to decompose (e.g. INFRA-157)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing files"),
) -> None:
    """
    Process a split-request JSON to generate child stories and a parent plan.
    """
    with tracer.start_as_current_span("decompose_story") as span:
        logger.info(
            f"Starting decomposition for {story_id}",
            extra={"event": "decompose_story_start", "story_id": story_id}
        )

        # 1. Discover split request (AC-1)
        split_request_path = config.cache_dir / "split_requests" / f"{story_id}.json"
        if not split_request_path.exists():
            console.print(f"[red]Error: No split request found for {story_id}.[/red]")
            console.print(f"Run 'agent new-runbook {story_id}' to generate one.")
            raise typer.Exit(code=1)

        try:
            with open(split_request_path, "r") as f:
                split_data: SplitRequest = json.load(f)
        except Exception as e:
            console.print(f"[red]Error reading split request: {e}[/red]")
            raise typer.Exit(code=1)

        suggestions = split_data.get("suggestions", [])
        reason = split_data.get("reason", "Decomposition requested by governance panel.")
        if not suggestions:
            console.print("[yellow]No suggestions found in split request. Nothing to do.[/yellow]")
            return

        # 2. Determine prefix and assign IDs (AC-2)
        prefix_match = re.match(r"^([A-Z]+)-", story_id)
        if not prefix_match:
            console.print(f"[red]Invalid story ID format: {story_id}[/red]")
            raise typer.Exit(code=1)
        prefix = prefix_match.group(1)

        child_ids = get_next_ids(prefix, len(suggestions))
        
        # 3. Idempotency guard (AC-6)
        conflicts: List[str] = []
        planned_operations: List[PlannedOperation] = []
        
        parent_story_path = find_story_file(story_id)
        if not parent_story_path:
            console.print(f"[red]Error: Could not find parent story file for {story_id}.[/red]")
            raise typer.Exit(code=1)

        parent_content = parent_story_path.read_text()
        parent_problem = _extract_section(parent_content, "## Problem Statement")
        parent_adrs = _extract_section(parent_content, "## Linked ADRs")

        for idx, suggestion in enumerate(suggestions):
            cid = child_ids[idx]
            slug = sanitize_title(suggestion)
            child_path = config.stories_dir / prefix / f"{cid}-{slug}.md"
            if child_path.exists():
                conflicts.append(str(child_path))
            
            planned_operations.append({
                "type": "STORY",
                "path": child_path,
                "id": cid,
                "title": suggestion,
                "content": _prepare_child_content(cid, suggestion, parent_problem, parent_adrs)
            })

        plan_path = config.plans_dir / prefix / f"{story_id}-plan.md"
        if plan_path.exists():
            conflicts.append(str(plan_path))
        
        planned_operations.append({
            "type": "PLAN",
            "path": plan_path,
            "id": story_id,
            "content": _prepare_plan_content(story_id, reason, planned_operations)
        })

        if conflicts:
            console.print("[red]Conflict detected. The following files already exist:[/red]")
            for c in conflicts:
                console.print(f" - {c}")
            raise typer.Exit(code=1)

        # 4. Dry-run mode (AC-7)
        if dry_run:
            console.print("[bold blue]DRY RUN - No changes will be written.[/bold blue]")
            for op in planned_operations:
                console.print(f"[green]Would create {op['type']}:[/green] {op['path']}")
            console.print(f"[yellow]Would update parent state to SUPERSEDED:[/yellow] {parent_story_path}")
            return

        # 5. Execution
        for op in planned_operations:
            op["path"].parent.mkdir(parents=True, exist_ok=True)
            with open(op["path"], "w") as f:
                f.write(op["content"])
            
            if op["type"] == "STORY":
                logger.info(
                    f"Created child story {op['id']}",
                    extra={"event": "decompose_story_child_created", "story_id": op['id']}
                )
            else:
                logger.info(
                    f"Created parent plan for {story_id}",
                    extra={"event": "decompose_story_plan_written", "story_id": story_id}
                )

        # 6. Update parent story state (AC-5)
        # update_story_state now accepts an optional annotation suffix so the
        # full persisted value becomes e.g. "SUPERSEDED (see plan: INFRA-157-plan.md)".
        update_story_state(
            story_id,
            "SUPERSEDED",
            annotation=f"(see plan: {story_id}-plan.md)",
        )

        # 7. Sync (AC-8)
        try:
            from agent.commands.utils import push_safe
            push_safe()
        except ImportError:
            logger.warning("push_safe utility not found. Skipping sync.")

        logger.info(
            f"Decomposition complete for {story_id}",
            extra={"event": "decompose_story_complete", "story_id": story_id}
        )
        console.print(f"[bold green]Successfully decomposed {story_id} into {len(suggestions)} stories.[/bold green]")

def _extract_section(content: str, header: str) -> str:
    """
    Extract a markdown section from content.
    """
    lines = content.splitlines()
    start_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == header:
            start_idx = i + 1
            break
    
    if start_idx == -1:
        return ""
    
    result = []
    for i in range(start_idx, len(lines)):
        if lines[i].startswith("## "):
            break
        result.append(lines[i])
    
    return "\n".join(result).strip()

def _prepare_child_content(cid: str, title: str, problem: str, adrs: str) -> str:
    """
    Prepare the content for a child story file.
    """
    template_path = config.templates_dir / "story-template.md"
    content = template_path.read_text() if template_path.exists() else ""
    
    # Simple replacement
    content = content.replace("STORY-XXX: Title", f"{cid}: {title}")
    content = content.replace("DRAFT", "DRAFT") # Ensure it's DRAFT
    content = content.replace("What problem are we solving?", problem or "See parent story.")
    content = content.replace("As a <user>, I want <capability> so that <value>.", title)
    
    if adrs:
        content = content.replace("- ADR-XXX", adrs)
        
    content = content.replace("{{ COPYRIGHT_HEADER }}", get_full_license_header().strip())
    return content

def _prepare_plan_content(parent_id: str, reason: str, operations: List[PlannedOperation]) -> str:
    """Prepare the content for the parent plan file.

    Args:
        parent_id: The story ID being decomposed (e.g. ``'INFRA-157'``).
        reason: Human-readable reason from the split-request JSON.
        operations: List of planned operations (used to build the child story table).

    Returns:
        Rendered markdown string ready to write to disk.
    """
    template_path = config.templates_dir / "plan-template.md"
    content = template_path.read_text() if template_path.exists() else ""

    content = content.replace("PLAN-XXX: Title", f"PLAN-{parent_id}: Decomposition Plan")
    content = content.replace("STORY-XXX", parent_id)

    # Add Rationale and Child Stories
    rationale_section = f"## Rationale\n\n{reason}\n\n## Child Stories\n\n"
    rationale_section += "| Story ID | Title | Status |\n|---|---|---|\n"
    for op in operations:
        if op["type"] == "STORY":
            rationale_section += f"| {op['id']} | {op['title']} | DRAFT |\n"

    content = content.replace("## Summary", rationale_section + "\n## Summary")
    content = content.replace("{{ COPYRIGHT_HEADER }}", get_full_license_header().strip())
    return content
