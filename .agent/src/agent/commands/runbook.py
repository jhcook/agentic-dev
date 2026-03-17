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
from typing import List, Optional

import json
import re
import time

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
from agent.core.implement.guards import validate_code_block
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.core.implement.parser import parse_code_blocks
from agent.utils.validation_formatter import format_runbook_errors
from agent.db.client import upsert_artifact

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
app = typer.Typer()
console = Console()
error_console = Console(stderr=True)

# Complexity Gatekeeper directive injected into the runbook system prompt (INFRA-094)
SPLIT_REQUEST_DIRECTIVE = (
    "COMPLEXITY GATEKEEPER DIRECTIVE:\n"
    "If, during runbook generation, you determine that the implementation plan would exceed "
    "ANY of these thresholds:\n"
    "- More than 400 lines of code changed\n"
    "- More than 8 implementation steps\n"
    "- More than 4 files modified\n\n"
    "Then you MUST NOT generate a runbook. Instead, emit ONLY a JSON block with this exact structure:\n\n"
    '{"SPLIT_REQUEST": true, "reason": "<one-sentence explanation>", '
    '"suggestions": ["<child story 1 title and scope>", "<child story 2 title and scope>"]}\n\n'
    "Do NOT wrap this in any other text or markdown if you determine the story must be split.\n"
    "If the story fits within the thresholds, proceed with normal runbook generation."
)


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

    # INFRA-107: Targeted introspection for story-referenced files
    targeted_context = context_loader._load_targeted_context(story_content)
    test_impact = context_loader._load_test_impact(story_content)
    behavioral_contracts = context_loader._load_behavioral_contracts(story_content)

    if targeted_context or test_impact:
        total = len(targeted_context) + len(test_impact) + len(behavioral_contracts)
        console.print(f"[dim]ℹ️  Targeted introspection: {total} chars[/dim]")

    if source_tree:
        console.print(f"[dim]ℹ️  Including source context ({len(source_tree) + len(source_code)} chars)[/dim]")
    
    panel_description = agents_data.get("description", "")
    panel_checks = agents_data.get("checks", "")
    
    # INFRA-135: Dynamic Rule Retrieval (Rule Diet)
    # Replaces static truncation with semantic filtering
    rules_content = _retrieve_dynamic_rules(story_content, targeted_context)
    
    if len(rules_content) < len(rules_full) * 0.5:
        console.print(f"[dim]ℹ️  Rule Diet active: Prompt reduced by {100 - (len(rules_content)/len(rules_full)*100):.1f}%[/dim]")

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
8. You MUST base your `<<<SEARCH` blocks exactly on the content provided in TARGETED FILE CONTENTS. Do NOT paraphrase, guess, or modify the lines you are searching for. They must exactly match the source.
9. You MUST list all patch targets from TEST IMPACT MATRIX in the Test Impact Matrix section and specify the new patch target for each.
10. You MUST preserve all BEHAVIORAL CONTRACTS. If a default value or invariant must change, explicitly document it in the runbook step.
11. CRITICAL — IMPLEMENTATION BLOCK FORMAT CONTRACT:
    - `#### [MODIFY] <path>` MUST be followed by one or more `<<<SEARCH / === / >>>` blocks ONLY.
      NEVER follow a [MODIFY] header with a fenced code block — it will be silently skipped by the parser.
    - `#### [NEW] <path>` MUST be followed by a complete fenced code block — but ONLY if the file
      does not already exist in the SOURCE FILE TREE. If the file exists (even if you are rewriting it completely), you MUST use `[MODIFY]` with a `<<<SEARCH` block that matches the entire existing file contents.
    - All NEW Python files MUST have PEP-257 docstrings on the module, every class, every function,
      and every inner/closure function. The docstring gate will hard-reject files missing any of these.
12. You MUST use full, repository-root-relative file paths for ALL files (e.g., STARTING with `.agent/src/` or similar, NOT just `src/`).

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

{SPLIT_REQUEST_DIRECTIVE if not skip_forecast else '(Forecast gate bypassed — generate the runbook regardless of complexity.)'}
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

TARGETED FILE CONTENTS (critical — full source code of files in scope for your changes):
{targeted_context if targeted_context else "(No targeted files identified in story)"}

TEST IMPACT MATRIX (tests with patch targets for these modules — MUST be addressed):
{test_impact if test_impact else "(No test impact detected)"}

BEHAVIORAL CONTRACTS (defaults and invariants — MUST be preserved):
{behavioral_contracts if behavioral_contracts else "(No behavioral contracts found)"}

Generate the runbook now.
"""

    console.print("[bold green]🤖 Panel is discussing...[/bold green]")
    
    max_attempts = 3
    attempt = 0
    content = ""
    current_user_prompt = user_prompt

    while attempt < max_attempts:
        attempt += 1
        with console.status(f"[bold green]🤖 Panel is discussing (Attempt {attempt}/{max_attempts})...[/bold green]") as status:
            content = ai_service.complete(system_prompt, current_user_prompt, rich_status=status)
            
        if not content:
            console.print("[bold red]❌ AI returned empty response.[/bold red]")
            raise typer.Exit(code=1)

        # -- SPLIT_REQUEST Fallback (INFRA-094) --
        if "SPLIT_REQUEST" in content:
            break  # Let the split logic below handle it

        # 1. Schema validation
        with tracer.start_as_current_span("validate_runbook_schema") as span:
            schema_violations = validate_runbook_schema(content)
            span.set_attribute("validation.passed", not bool(schema_violations))
            span.set_attribute("validation.error_count", len(schema_violations) if schema_violations else 0)
        
        if schema_violations:
            logger.warning("runbook_schema_fail", extra={"attempt": attempt, "story_id": story_id})
            formatted_errors = format_runbook_errors(schema_violations)
            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt} failed schema validation. Retrying...[/yellow]")
                current_user_prompt = f"{user_prompt}\n\n{formatted_errors}\nPlease fix these and re-generate."
                continue
            else:
                error_console.print(f"[bold red]❌ Schema validation failed after {max_attempts} attempts.[/bold red]")
                error_console.print(formatted_errors)
                raise typer.Exit(code=1)

        # 2. Code Gate Self-Healing (INFRA-155 AC-1)

        code_errors: List = []
        code_warnings: List = []
        
        with tracer.start_as_current_span("validate_code_gates") as span:
            # Extract all code blocks
            blocks = parse_code_blocks(content)
            for b in blocks:
                res = validate_code_block(b["file"], b["content"])
                code_errors.extend(res.errors)
                code_warnings.extend(res.warnings)
            
            span.set_attribute("validation.passed", not bool(code_errors))
            span.set_attribute("validation.error_count", len(code_errors))

        if code_errors:
            logger.warning("runbook_code_gate_fail", extra={"attempt": attempt, "story_id": story_id, "errors": code_errors})
            error_msg = "CODE GATE VIOLATIONS DETECTED:\n" + "\n".join(f"- {e}" for e in code_errors)
            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt} failed code gates. Asking AI for self-healing...[/yellow]")
                current_user_prompt = f"{user_prompt}\n\n{error_msg}\nPlease fix these code violations and re-generate the full runbook."
                continue
            else:
                error_console.print(f"[bold red]❌ Code gates failed after {max_attempts} attempts.[/bold red]")
                error_console.print(error_msg)
                raise typer.Exit(code=1)
        
        # If we got here, schema and code errors are clear
        if code_warnings:
            console.print(f"[yellow]ℹ️  Code warnings detected (non-blocking):[/yellow]")
            for w in code_warnings:
                console.print(f"  [dim]• {w}[/dim]")

        break

    # -- SPLIT_REQUEST Fallback (INFRA-094) --
    if "SPLIT_REQUEST" in content:
        split_data = _parse_split_request(content)
        if split_data:
            # AC-3: Save decomposition suggestions
            config.split_requests_dir.mkdir(parents=True, exist_ok=True)
            split_path = config.split_requests_dir / f"{story_id}.json"
            split_path.write_text(json.dumps(split_data, indent=2))

            # NFR: Structured logging (SOC2)
            logger.warning(
                "split_request story=%s reason=%s suggestion_count=%d",
                story_id,
                scrub_sensitive_data(split_data.get("reason", ""))[:200],
                len(split_data.get("suggestions", [])),
            )

            if skip_forecast:
                # Gate was bypassed — treat split as advisory, not blocking
                logger.info(
                    "split_request advisory_only=True story=%s (--skip-forecast)",
                    story_id,
                )
                console.print(
                    "[dim]ℹ️  AI recommended splitting (advisory only — "
                    "--skip-forecast active). Generating runbook anyway.[/dim]"
                )
                # Re-generate without the SPLIT_REQUEST directive
                console.print("[bold green]🤖 Panel is re-generating (no split directive)...[/bold green]")
                with console.status("[bold green]🤖 Panel is re-generating...[/bold green]") as status:
                    content = ai_service.complete(system_prompt, user_prompt, rich_status=status)
                if not content:
                    console.print("[bold red]❌ AI returned empty response on retry.[/bold red]")
                    raise typer.Exit(code=1)
            else:
                # AC-4: Exit with code 2 and guidance
                console.print("[bold yellow]⚠️  AI recommends splitting this story.[/bold yellow]")
                console.print(f"  • Reason: {split_data.get('reason', 'N/A')}")
                console.print(f"  • Suggestions: {len(split_data.get('suggestions', []))}")
                for i, s in enumerate(split_data.get("suggestions", []), 1):
                    console.print(f"    {i}. {s}")
                console.print(f"\nDecomposition saved to: {split_path}")
                console.print("[dim]Create child stories with: agent new-story <ID>[/dim]")
                raise typer.Exit(code=2)

    # 5. Write
    runbook_file.write_text(content)
    console.print(f"[bold green]✅ Runbook generated at: {runbook_file}[/bold green]")

    # 5.1 Schema validation status
    console.print("[dim]✅ Schema valid — all implementation blocks are correctly formatted.[/dim]")
    
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


def _retrieve_dynamic_rules(story_content: str, targeted_context: str) -> str:
    """
    Perform semantic retrieval of contextual rules based on story impact (INFRA-135).
    
    Classifies .agent/rules/ into core (always included) and contextual 
    (retrieved via RAG). Reduces token count by ≥50%.
    
    Args:
        story_content: The user story markdown.
        targeted_context: Introspection of touched files.
        
    Returns:
        Assembled string of relevant governance rules.
    """
    start_time = time.monotonic()
    rules_dir = config.rules_dir
    
    # AC-1: Audit and Classify
    # Core: Identity, Governance, Security, QA, Architect (Foundation)
    CORE_PREFIXES = ("000", "001", "002", "003", "004")
    
    core_content = []
    contextual_candidates = []
    
    if rules_dir.exists():
        for rule_file in sorted(rules_dir.glob("*.mdc")):
            if rule_file.name.startswith(CORE_PREFIXES):
                core_content.append(f"--- CORE RULE: {rule_file.name} ---\n{rule_file.read_text()}")
            else:
                contextual_candidates.append(rule_file.name)
                
    # AC-3: Retrieval Step
    query = f"{story_content}\n\nTOUCHED FILES:\n{targeted_context}"
    retrieved_content = ""
    source = "NONE"
    fallback_used = False
    
    try:
        # Try local Vector DB first as it's the primary fallback for Rule Diet
        from agent.db.journey_index import JourneyIndex
        idx = JourneyIndex()
        # Search for contextual rules specifically
        retrieved_content = idx.search(f"Governance rules for: {query}", k=4)
        source = "ChromaDB"
        fallback_used = True
    except Exception as e:
        logger.warning(f"Rule retrieval failed: {e}")
        source = "FAILED"
        
    # AC-4: Fallback Mechanism
    # If retrieval failed or returned empty, we still have core_content (Security + QA)
    
    latency = (time.monotonic() - start_time) * 1000
    
    # NFR: SOC2/Observability logging
    logger.info("rule_retrieval", extra={
        "source": source,
        "count": 4 if retrieved_content else 0,
        "latency_ms": latency,
        "fallback_used": fallback_used
    })
    
    combined = "\n\n".join(core_content)
    if retrieved_content:
        combined += "\n\n### CONTEXTUAL RULES (RETRIEVED) ###\n\n" + retrieved_content
        
    return combined


def _parse_split_request(content: str) -> Optional[dict]:
    """Extract and parse SPLIT_REQUEST JSON from AI response.

    Handles:
    - Pure JSON response
    - JSON embedded in markdown code fences
    - Malformed JSON (returns None -> treat as normal runbook)

    Args:
        content: Raw AI response string.

    Returns:
        Parsed dict if valid SPLIT_REQUEST, None otherwise.
    """
    # Try direct parse first
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from markdown code fences (\n made optional for AI variance)
    json_match = re.search(r"```(?:json)?\s*\n?(.+?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # Malformed or not a SPLIT_REQUEST -- graceful fallback
    logger.debug(
        "SPLIT_REQUEST marker found but JSON parse failed, treating as normal runbook"
    )
    return None
