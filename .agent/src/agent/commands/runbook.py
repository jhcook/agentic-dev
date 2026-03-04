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

from dataclasses import dataclass
from typing import Optional

import re

import typer
from opentelemetry import trace
from rich.console import Console

# from agent.core.ai import ai_service # Moved to local import
from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.utils import (
    find_story_file,
    scrub_sensitive_data,
    get_copyright_header,
)
from agent.core.context import context_loader
from agent.db.client import upsert_artifact

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
app = typer.Typer()
console = Console()


@dataclass
class ComplexityMetrics:
    """Heuristic complexity metrics for a story."""

    step_count: int
    context_width: int
    verb_intensity: float
    estimated_loc: float
    file_count: int


def score_story_complexity(content: str) -> ComplexityMetrics:
    """Calculate heuristic complexity score from story content.

    Scoring is regex-based and runs in <100ms (no AI call).

    Args:
        content: Raw story markdown content.

    Returns:
        ComplexityMetrics with step_count, context_width, verb_intensity,
        estimated_loc, and file_count.
    """
    with tracer.start_as_current_span("forecast.score_complexity") as span:
        step_count = len(re.findall(r"^\s*-\s*\[ \]", content, re.MULTILINE))
        context_width = len(re.findall(r"ADR-\d+|JRN-\d+", content))

        verb_intensity = 1.0
        if re.search(r"\bmigrate\b", content, re.IGNORECASE):
            verb_intensity = 2.0
        elif re.search(r"\brefactor\b", content, re.IGNORECASE):
            verb_intensity = 1.5

        file_count = len(re.findall(r"####\s*\[(?:MODIFY|NEW|DELETE|ADD)\]", content))
        estimated_loc = (step_count * 40) * verb_intensity

        span.set_attribute("forecast.step_count", step_count)
        span.set_attribute("forecast.context_width", context_width)
        span.set_attribute("forecast.verb_intensity", verb_intensity)
        span.set_attribute("forecast.estimated_loc", estimated_loc)
        span.set_attribute("forecast.file_count", file_count)

        logger.info(
            "forecast step_count=%d context_width=%d verb_intensity=%.1f "
            "estimated_loc=%.0f file_count=%d",
            step_count, context_width, verb_intensity, estimated_loc, file_count,
        )

        return ComplexityMetrics(
            step_count=step_count,
            context_width=context_width,
            verb_intensity=verb_intensity,
            estimated_loc=estimated_loc,
            file_count=file_count,
        )


def generate_decomposition_plan(story_id: str, story_content: str) -> str:
    """Generate a decomposition plan for an over-budget story using AI.

    Args:
        story_id: The story identifier (e.g. INFRA-093).
        story_content: Raw story markdown content.

    Returns:
        Path to the generated plan file.
    """
    from agent.core.ai import ai_service  # ADR-025: lazy init

    scope_match = re.match(r"([A-Z]+)-\d+", story_id)
    scope = scope_match.group(1) if scope_match else "MISC"
    plan_dir = config.plans_dir / scope
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{story_id}-plan.md"

    system_prompt = (
        "You are a story decomposer. Given a story that exceeds complexity "
        "limits, produce a Plan with child stories. Each child must be "
        "scoped to ≤400 LOC. Output markdown with child story references."
    )
    user_prompt = f"Decompose this story:\n\n{story_content}"

    plan_content = ai_service.complete(system_prompt, user_prompt)
    if plan_content:
        plan_path.write_text(plan_content)
    else:
        plan_path.write_text(f"# Plan: {story_id}\n\nAI returned empty plan.")

    return str(plan_path)

def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    skip_forecast: bool = typer.Option(
        False, "--skip-forecast", help="Bypass the complexity forecast gate."
    ),
):
    """
    Generate an implementation runbook using AI Governance Panel.
    """
    # 0. Configure Provider Override if set
    from agent.core.ai import ai_service  # ADR-025: lazy init
    if provider:
        ai_service.set_provider(provider)
    
    # 1. Find Story
    story_file = find_story_file(story_id)
    if not story_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         raise typer.Exit(code=1)

    # 1.1 Enforce Story State
    story_text = story_file.read_text()
    
    # Check for both formats: "State: COMMITTED" (inline) and "## State\nCOMMITTED" (multiline)
    state_pattern = r"(?:^State:\s*COMMITTED|^## State\s*\n+COMMITTED|^Status:\s*COMMITTED)"
    if not re.search(state_pattern, story_text, re.MULTILINE):
        console.print(f"[bold red]❌ Story {story_id} is not COMMITTED. Please commit the story before creating a runbook.[/bold red]")
        raise typer.Exit(code=1)

    # 1.2 Forecast Gate (INFRA-093)
    metrics = score_story_complexity(story_text)
    is_over_budget = (
        metrics.estimated_loc > 400
        or metrics.step_count > 8
        or metrics.file_count > 4
    )

    if is_over_budget and not skip_forecast:
        logger.warning(
            "forecast gate_decision=FAIL story=%s estimated_loc=%.0f "
            "step_count=%d file_count=%d",
            story_id, metrics.estimated_loc, metrics.step_count, metrics.file_count,
        )
        plan_path = generate_decomposition_plan(story_id, story_text)
        console.print("[bold red]Story exceeds complexity budget.[/bold red]")
        console.print(f"  • Estimated LOC: {metrics.estimated_loc:.0f} (Max: 400)")
        console.print(f"  • Steps: {metrics.step_count} (Max: 8)")
        console.print(f"  • Files: {metrics.file_count} (Max: 4)")
        console.print(f"\nDecomposition plan generated at: {plan_path}")
        raise typer.Exit(code=2)

    if skip_forecast:
        from agent.commands.gates import log_skip_audit
        log_skip_audit("runbook_forecast", story_id)
        logger.info("forecast gate_decision=SKIP story=%s", story_id)
    else:
        logger.info("forecast gate_decision=PASS story=%s", story_id)
        console.print("[green]✅ Forecast gate passed.[/green]")

    # 2. Check Paths
    scope = story_file.parent.name
    runbook_dir = config.runbooks_dir / scope
    runbook_dir.mkdir(parents=True, exist_ok=True)
    runbook_file = runbook_dir / f"{story_id}-runbook.md"
    
    if runbook_file.exists():
        console.print(f"[yellow]⚠️  Runbook already exists at {runbook_file}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(code=0)

    # 3. Context — single source via context_loader
    console.print(f"🛈 invoking AI Governance Panel for {story_id}...")
    story_content = scrub_sensitive_data(story_file.read_text())
    import asyncio
    ctx = asyncio.run(context_loader.load_context())
    rules_full = ctx.get("rules", "")
    agents_data = ctx.get("agents", {})
    instructions_content = ctx.get("instructions", "")
    adrs_content = ctx.get("adrs", "")
    source_tree = ctx.get("source_tree", "")
    source_code = ctx.get("source_code", "")
    
    if source_tree:
        console.print(f"[dim]ℹ️  Including source context ({len(source_tree) + len(source_code)} chars)[/dim]")
    
    panel_description = agents_data.get("description", "")
    panel_checks = agents_data.get("checks", "")
    
    # Truncate rules to avoid token limits (GitHub CLI has 8000 token max)
    rules_content = rules_full[:3000] + "\n\n[...truncated for token limits...]" if len(rules_full) > 3000 else rules_full

    # 4. Prompt
    # Load Template
    template_path = config.templates_dir / "runbook-template.md"
    if not template_path.exists():
        console.print(f"[bold red]❌ Runbook template not found at {template_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_content = template_path.read_text()
    template_content = template_content.replace("{{ COPYRIGHT_HEADER }}", get_copyright_header())
    
    system_prompt = f"""You are the AI Governance Panel for this repository.
Your role is to design and document a DETAILED Implementation Runbook for a software engineering task.

THE PANEL (You represent ALL these roles):
{panel_description}

GOVERNANCE CHECKS PER ROLE:
{panel_checks}

INSTRUCTIONS:
1. You MUST adopt the perspective of EVERY role in the panel.
2. You MUST provide a distinct review section for EVERY role.
3. You MUST enforce the "Definition of Done".
4. You MUST follow the structure of the provided TEMPLATE exactly.
5. You MUST respect all Architectural Decision Records (ADRs) as codified decisions.
6. You MUST follow the DETAILED ROLE INSTRUCTIONS for each role.
7. You MUST use the SOURCE CODE CONTEXT to derive accurate file paths, existing patterns, and SDK usage. Do NOT invent file paths or SDK calls — use only what appears in the source tree and code outlines.

INPUTS:
1. User Story (Requirements)
2. Governance Rules (Compliance constraints)
3. Role Instructions (Per-role detailed guidance)
4. ADRs (Codified architectural decisions)
5. Source File Tree (Repository structure)
6. Source Code Outlines (Imports, class/function signatures)

TEMPLATE STRUCTURE (Found in {template_path.name}):
{template_content}

Your output must be the FILLED IN template, starting with the Header. Do NOT wrap in markdown blocks.
Replace placeholders like <Title>, <Clear summary...>, etc. with actual content.
Update '## Panel Review Findings' with specific commentary.
Update '## Targeted Refactors & Cleanups (INFRA-043)' with any relevant cleanups found.
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

GOVERNANCE RULES:
{rules_content}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}

EXISTING USER JOURNEYS:
{_load_journey_context()}

SOURCE FILE TREE:
{source_tree if source_tree else "(No source directory found)"}

SOURCE CODE OUTLINES:
{source_code if source_code else "(No source files found)"}

Generate the runbook now.
"""

    console.print("[bold green]🤖 Panel is discussing...[/bold green]")
    with console.status("[bold green]🤖 Panel is discussing...[/bold green]"):
        content = ai_service.complete(system_prompt, user_prompt)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)

    # 5. Write
    runbook_file.write_text(content)
    console.print(f"[bold green]✅ Runbook generated at: {runbook_file}[/bold green]")
    
    # Auto-sync
    runbook_id = f"{story_id}" # Using Story ID for Runbook ID as well, with type='runbook'
    if upsert_artifact(runbook_id, "runbook", content, author="agent"):
         console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
         console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    console.print("[yellow]⚠️  ACTION REQUIRED: Review and change to '## State\\nACCEPTED'.[/yellow]")


def _load_journey_context() -> str:
    """Load existing journey YAML files for context injection.
    
    Returns a size-bounded, scrubbed string of journey content.
    """
    from agent.core.utils import scrub_sensitive_data

    journeys_content = ""
    if config.journeys_dir.exists():
        for jf in config.journeys_dir.rglob("*.yaml"):
            journeys_content += f"\n---\n{jf.read_text()}"

    if journeys_content:
        return scrub_sensitive_data(journeys_content[:5000])
    return "None defined yet."
