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

"""CLI command for generating implementation runbooks.

Orchestrates context loading, AI generation (chunked or monolithic),
validation gates, and artifact syncing. Heavy logic is delegated to:
- ``runbook_helpers``: complexity scoring, decomposition, rule diet
- ``runbook_gates``: schema/code/S/R/DoD validation gates
- ``runbook_generation``: chunked two-phase pipeline
"""

from pathlib import Path
from typing import List, Optional

import json
import os
import re
import time

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.utils import (
    find_story_file,
    scrub_sensitive_data,
    get_copyright_header,
)
from agent.commands.utils import (
    auto_fix_changelog_step,
    auto_fix_license_headers,
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
)
from agent.core.context import context_loader
from agent.core.implement.guards import (
    autocorrect_runbook_fences,
    lint_runbook_syntax,
    validate_and_correct_sr_blocks,
)
from agent.core.implement.retry import MaxRetriesExceededError
from agent.db.client import upsert_artifact
from agent.commands.runbook_helpers import (
    generate_decomposition_plan,
    load_journey_context,
    parse_split_request,
    retrieve_dynamic_rules,
    score_story_complexity,
)
from agent.commands.runbook_gates import (
    run_generation_gates,
    run_dod_gate,
    handle_split_request,
)
from agent.commands.runbook_generation import generate_runbook_chunked
from agent.core.implement.parser import validate_runbook_schema
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
app = typer.Typer()
console = Console()
error_console = Console(stderr=True)

try:
    from observability.telemetry import setup_telemetry as _setup_telemetry
    _setup_telemetry(service_name="agent-cli")
except Exception:  # noqa: BLE001 — OTel init must never crash the CLI
    pass

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
    '"estimated_loc": <number>, "estimated_files": <number>, '
    '"suggestions": ["<child story 1 title and scope>", "<child story 2 title and scope>"]}\n\n'
    "Do NOT wrap this in any other text or markdown if you determine the story must be split.\n"
    "If the story fits within the thresholds, proceed with normal runbook generation."
)


def _write_and_sync(
    content: str,
    story_id: str,
    story_file: Path,
    runbook_file: Path,
) -> None:
    """Lint, write, sync, and back-populate a generated runbook.

    Args:
        content: The generated runbook markdown.
        story_id: The story identifier.
        story_file: Path to the story file.
        runbook_file: Path to the runbook output file.
    """
    # Post-generation lint: autocorrect then report remaining issues
    content, corrections = autocorrect_runbook_fences(content)
    for fix in corrections:
        console.print(f"[dim]🔧 Auto-fixed: {fix}[/dim]")
    # Post-generation S/R validation: auto-correct hallucinated SEARCH text
    # (Layer 1 prevents most hallucinations; Layer 2 AI-reanchors the rest)
    content, sr_total, sr_corrected = validate_and_correct_sr_blocks(content, threshold=0.80)
    if sr_total > 0:
        console.print(
            f"[dim]🔍 S/R validation: {sr_total} block(s) checked, "
            f"{sr_corrected} auto-corrected[/dim]"
        )

    # Layer 3 hard gate: if unfixable S/R blocks remain, refuse to write.
    # Import here to avoid circular dependency.
    from agent.commands.utils import validate_sr_blocks as gate_validate_sr
    remaining_mismatches = gate_validate_sr(content)
    # Filter: only block on true SEARCH mismatches. REPLACE-side semantic errors
    # (import/syntax/signature/regression) are advisory — SEARCH matched means structurally sound.
    real_failures = [
        m for m in remaining_mismatches
        if not m.get("missing_modify")
        and not m.get("parse_error")
        and not m.get("replace_syntax_error")
        and not m.get("replace_import_error")
        and not m.get("replace_signature_error")
        and not m.get("replace_regression_warning")
    ]
    sem_advisory = [
        m for m in remaining_mismatches
        if not m.get("missing_modify") and not m.get("parse_error")
        and (m.get("replace_syntax_error") or m.get("replace_import_error")
             or m.get("replace_signature_error") or m.get("replace_regression_warning"))
    ]
    for m in sem_advisory:
        if m.get("replace_import_error"):
            console.print(f"[dim]⚠️  {m['file']}: REPLACE imports unresolved symbol (may be created in another block)[/dim]")
        if m.get("replace_syntax_error"):
            console.print(f"[dim]⚠️  {m['file']}: REPLACE produces syntax advisory — review manually[/dim]")
        if m.get("replace_regression_warning"):
            console.print(f"[dim]⚠️  {m['file']}: REPLACE regression advisory — stub may be incomplete[/dim]")
    if real_failures:
        console.print(
            f"[bold red]❌ {len(real_failures)} S/R block(s) still failed after "
            f"fuzzy + AI correction:[/bold red]"
        )
        for m in real_failures[:5]:  # Show max 5
            console.print(f"  [red]• {m['file']} (block #{m['index']})[/red]")
        logger.error(
            "sr_hard_gate_failed",
            extra={
                "story_id": story_id,
                "failures": len(real_failures),
                "files": list({m["file"] for m in real_failures}),
            },
        )
        # Still write so work isn't lost, but signal failure
        runbook_file.write_text(content)
        console.print(
            f"[yellow]⚠️  Runbook written to {runbook_file} "
            f"(S/R failures present — review required)[/yellow]"
        )
        raise typer.Exit(code=1)

    lint_errors = lint_runbook_syntax(content)
    if lint_errors:
        console.print("[bold red]❌ Runbook lint errors (post-autocorrect):[/bold red]")
        for err in lint_errors:
            console.print(f"  [red]• {err}[/red]")
        logger.error("runbook_lint_errors story=%s count=%d", story_id, len(lint_errors))
        # Still write the file so work isn't lost, but signal failure
        runbook_file.write_text(content)
        console.print(f"[yellow]⚠️  Runbook written to {runbook_file} (lint errors present — review required)[/yellow]")
        raise typer.Exit(code=1)

    # ── In-memory normalization (before write) ───────────────────────────────
    # Collapse 3+ consecutive blank lines to max 2 (MD012), preserving code
    # fences verbatim. Then enforce exactly one trailing newline.
    import re as _re
    _fence_split = _re.split(r'(^```[^\n]*\n.*?^```)', content, flags=_re.MULTILINE | _re.DOTALL)
    normalized_parts = []
    for part in _fence_split:
        if part.startswith('```'):
            normalized_parts.append(part)  # Inside fence — never touch
        else:
            normalized_parts.append(_re.sub(r'\n{3,}', '\n\n', part))
    content = ''.join(normalized_parts)
    content = content.rstrip('\n') + '\n'

    runbook_file.write_text(content)
    console.print(f"[bold green]✅ Runbook generated at: {runbook_file}[/bold green]")

    # Back-populate story with identified ADRs and Journeys (INFRA-158)
    try:
        adrs = extract_adr_refs(content)
        journeys = extract_journey_refs(content)
        if adrs or journeys:
            merge_story_links(story_file, adrs, journeys)
            logger.info(
                "story_links_updated",
                extra={
                    "story_id": story_id,
                    "adrs": sorted(adrs),
                    "journeys": sorted(journeys),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("story_links_update_failed story=%s error=%s", story_id, exc)

    console.print("[dim]✅ Schema valid — all implementation blocks are correctly formatted.[/dim]")

    if upsert_artifact(story_id, "runbook", content, author="agent"):
        console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
        console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    console.print("[yellow]\u26a0\ufe0f  ACTION REQUIRED: Review and change to '## State\\nACCEPTED'.[/yellow]")


def _validate_version_compatibility(skeleton_version: str) -> None:
    """Enforce version-controlled schema tags."""
    with open(os.path.join(os.path.dirname(__file__), "../../VERSION"), "r") as f:
        lines = f.readlines()
        min_ver = lines[1].split(":")[1].strip() if len(lines) > 1 else "1.0.0"
    
    if skeleton_version < min_ver:
        raise InvalidTemplateError(f"Skeleton version {skeleton_version} is below minimum {min_ver}")

def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    skip_forecast: bool = typer.Option(
        False, "--skip-forecast", help="Bypass the complexity forecast gate."
    ),
    timeout: int = typer.Option(
        180, "--timeout", help="AI request timeout in seconds (default: 180)."
    ),
    legacy_gen: bool = typer.Option(
        False, "--legacy-gen",
        help="Skip chunked generation and use single-pass monolithic mode.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Force regeneration even if runbook already exists and is valid.",
    ),
):
    """Generate an implementation runbook using AI Governance Panel."""
    # 0. Configure Provider Override if set
    from agent.core.ai import ai_service  # ADR-025: lazy init
    if provider:
        ai_service.set_provider(provider)
    import os as _os
    _os.environ["AGENT_AI_TIMEOUT_MS"] = str(timeout * 1000)

    # 1. Find Story
    story_file = find_story_file(story_id)
    if not story_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         raise typer.Exit(code=1)

    # 1.1 Enforce Story State
    story_text = story_file.read_text()
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

    if runbook_file.exists() and not force:
        # Convergent idempotency: validate existing runbook before regenerating
        console.print(f"[yellow]⚠️  Runbook already exists at {runbook_file}[/yellow]")
        console.print("[cyan]🔍 Validating existing runbook...[/cyan]")
        from agent.core.implement.parser import (
            validate_runbook_schema,
            parse_search_replace_blocks,
        )
        from agent.core.implement.orchestrator import resolve_path
        existing_content = runbook_file.read_text()
        issues = []

        # 1. Schema validation
        schema_errors = validate_runbook_schema(existing_content)
        if schema_errors:
            issues.extend([f"Schema: {e}" for e in schema_errors])

        # 2. [NEW] file targeting existing files
        new_paths = re.findall(
            r'####\s+\[NEW\]\s+(.+?)(?:\n|$)', existing_content
        )
        for raw_path in new_paths:
            path = raw_path.strip().strip('`')
            resolved = resolve_path(path)
            if resolved and resolved.exists():
                issues.append(
                    f"[NEW] targets existing file: {path}"
                )

        # 3. S/R block fidelity — check SEARCH text matches actual files
        sr_blocks = parse_search_replace_blocks(existing_content)
        for sr in sr_blocks:
            sr_path = sr.get("path", "")
            resolved = resolve_path(sr_path)
            if resolved and resolved.exists() and resolved.is_file():
                file_content = resolved.read_text()
                for block in sr.get("blocks", []):
                    search = block.get("search", "")
                    replace = block.get("replace", "")
                    if search not in file_content and replace not in file_content:
                        issues.append(
                            f"S/R mismatch: SEARCH not found in {sr_path} "
                            f"(and REPLACE not present either)"
                        )

        if not issues:
            console.print("[bold green]✅ Existing runbook is valid. No regeneration needed.[/bold green]")
            console.print(f"   Use --force to regenerate anyway.")
            logger.info("runbook_validation_pass story=%s", story_id)
            raise typer.Exit(code=0)
        else:
            console.print(f"[bold yellow]⚠️  Found {len(issues)} issue(s):[/bold yellow]")
            for issue in issues:
                console.print(f"  • {issue}")
            console.print(
                "\n[bold]Use --force to regenerate the runbook.[/bold]"
            )
            logger.warning(
                "runbook_validation_fail story=%s issues=%d",
                story_id, len(issues),
            )
            raise typer.Exit(code=1)
    elif runbook_file.exists() and force:
        console.print(f"[yellow]⚠️  --force: Overwriting existing runbook at {runbook_file}[/yellow]")
        logger.info("runbook_force_regenerate story=%s", story_id)
        # Note: .partial checkpoint is intentionally preserved here.
        # --force only unlocks the "already exists" gate; resume from checkpoint
        # is independent and automatic. To discard the checkpoint and start truly
        # fresh, delete the .partial file manually before running.
        _checkpoint = runbook_file.with_suffix(".partial")
        if _checkpoint.exists():
            console.print(f"[dim]⏩ .partial checkpoint found — generation will resume from it.[/dim]")

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

    # INFRA-107: Targeted introspection
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
    rules_content = retrieve_dynamic_rules(story_content, targeted_context)

    if len(rules_content) < len(rules_full) * 0.5:
        console.print(f"[dim]ℹ️  Rule Diet active: Prompt reduced by {100 - (len(rules_content)/len(rules_full)*100):.1f}%[/dim]")

    # INFRA-160: Catalogue Injection functionality has been disabled.
    j_catalogue, j_count = "", 0
    a_catalogue, a_count = "", 0

    # AC-3: Story links pre-seeded
    preseeded_adrs = extract_adr_refs(story_content)
    preseeded_journeys = extract_journey_refs(story_content)
    preseeded_block = ""
    if preseeded_adrs or preseeded_journeys:
        preseeded_block = "PRE-SEEDED STORY LINKS (Preserve these unless explicitly redundant):\n"
        if preseeded_adrs:
            preseeded_block += f"- ADRs: {', '.join(sorted(preseeded_adrs))}\n"
        if preseeded_journeys:
            preseeded_block += f"- Journeys: {', '.join(sorted(preseeded_journeys))}\n"

    # 4. Content Generation
    # ── Chunked path ──
    if not legacy_gen:
        console.print("[bold blue]🚀 Starting phased generation (concurrency enabled)...[/bold blue]")
        try:
            # INFRA-169: Phased generation engine (synchronous — no asyncio.run needed).
            # Internal chunk-level retries are handled by the orchestrator; fatal exhaustion bubbles here.
            checkpoint_path = runbook_file.with_suffix(".partial")
            content = generate_runbook_chunked(
                story_id=story_id,
                story_content=story_content,
                rules_content=rules_content,
                targeted_context=targeted_context,
                source_tree=source_tree,
                source_code=source_code,
                provider=provider,
                timeout=timeout,
                checkpoint_path=checkpoint_path,
            )
            # Clean up checkpoint on success — it's now in the final runbook file
            if checkpoint_path.exists():
                checkpoint_path.unlink(missing_ok=True)

            # -- SPLIT_REQUEST Fallback in Chunked (INFRA-094) --
            if "SPLIT_REQUEST" in content:
                from agent.commands.runbook_helpers import parse_split_request
                split_data = parse_split_request(content)
                if split_data:
                    config.split_requests_dir.mkdir(parents=True, exist_ok=True)
                    split_path = config.split_requests_dir / f"{story_id}.json"
                    split_path.write_text(json.dumps(split_data, indent=2))

                    logger.warning(
                        "split_request story=%s reason=%s suggestion_count=%d",
                        story_id,
                        scrub_sensitive_data(split_data.get("reason", ""))[:200],
                        len(split_data.get("suggestions", [])),
                    )

                    if skip_forecast:
                        logger.info(
                            "split_request advisory_only=True story=%s (--skip-forecast)",
                            story_id,
                        )
                        console.print(
                            "[dim]ℹ️  AI recommended splitting (advisory only — "
                            "--skip-forecast active). Chunked path cannot currently retry without it. Failing.[/dim]"
                        )
                        console.print("[bold red]❌ Advisory only not fully supported in chunked mode yet.[/bold red]")
                        raise typer.Exit(code=1)
                    else:
                        console.print("[bold yellow]⚠️  AI recommends splitting this story.[/bold yellow]")
                        console.print(f"  • Reason: {split_data.get('reason', 'N/A')}")
                        est_loc = split_data.get('estimated_loc')
                        est_files = split_data.get('estimated_files')
                        if est_loc or est_files:
                            console.print(f"  • Estimated scope: ~{est_loc or '?'} LOC across {est_files or '?'} files")
                        console.print(f"  • Suggestions: {len(split_data.get('suggestions', []))}")
                        for i, s in enumerate(split_data.get("suggestions", []), 1):
                            console.print(f"    {i}. {s}")
                        console.print(f"\nDecomposition saved to: {split_path}")
                        console.print("[dim]Create child stories with: agent new-story <ID>[/dim]")
                        raise typer.Exit(code=2)
                        
            _write_and_sync(content, story_id, story_file, runbook_file)
            return
        except MaxRetriesExceededError as e:
            from agent.core.implement.security import sanitize_error_message
            from rich.markup import escape as _esc
            console.print(f"\n[bold red]Runbook generation failed after retries: {_esc(sanitize_error_message(e))}[/bold red]")
            logger.error("runbook_generation_max_retries_exceeded", extra={"story_id": story_id})
            raise typer.Exit(code=1)
        except (typer.Exit, SystemExit):
            raise  # Let controlled exits propagate without wrapping
        except Exception as e:
            from agent.core.implement.security import sanitize_error_message
            from rich.markup import escape as _esc
            console.print(f"\n[bold red]Unexpected generation error: {_esc(sanitize_error_message(e))}[/bold red]")
            logger.exception("runbook_generation_unexpected_error", extra={"story_id": story_id})
            raise typer.Exit(code=1)

    # ── Monolithic path ──
    content = _run_monolithic_generation(
        story_id=story_id,
        story_content=story_content,
        story_file=story_file,
        runbook_file=runbook_file,
        rules_content=rules_content,
        instructions_content=instructions_content,
        adrs_content=adrs_content,
        source_tree=source_tree,
        source_code=source_code,
        targeted_context=targeted_context,
        test_impact=test_impact,
        behavioral_contracts=behavioral_contracts,
        panel_description=panel_description,
        panel_checks=panel_checks,
        preseeded_block=preseeded_block,
        j_catalogue=j_catalogue,
        a_catalogue=a_catalogue,
        skip_forecast=skip_forecast,
        timeout=timeout,
    )

    _write_and_sync(content, story_id, story_file, runbook_file)


def _run_monolithic_generation(
    *,
    story_id: str,
    story_content: str,
    story_file: Path,
    runbook_file: Path,
    rules_content: str,
    instructions_content: str,
    adrs_content: str,
    source_tree: str,
    source_code: str,
    targeted_context: str,
    test_impact: str,
    behavioral_contracts: str,
    panel_description: str,
    panel_checks: str,
    preseeded_block: str,
    j_catalogue: str,
    a_catalogue: str,
    skip_forecast: bool,
    timeout: int,
) -> str:
    """Run the legacy monolithic single-pass generation with gate loop.

    Args:
        All context and configuration needed for prompt building and gate validation.

    Returns:
        The fully validated runbook content.
    """
    from agent.core.ai import ai_service

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
13. NEVER include steps that modify files in `.agent/cache/` (stories, plans, runbooks). Story state transitions are managed automatically by `agent` commands — do NOT add `[MODIFY]` or `[NEW]` steps for any file under `.agent/cache/`.
14. MANDATORY TEST COVERAGE — For every `[NEW] <path/to/impl>` step you write (where the file
    is NOT itself a test file), you MUST include a paired `[NEW] <path/to/tests/test_impl>` step
    in the SAME runbook. Rules:
    - The test file MUST use the project's test framework and cover every public interface in the implementation.
    - The test file MUST be placed in the `tests/` subdirectory adjacent to the implementation file.
    - This is machine-verified — a runbook missing any paired test file will be rejected and sent back
      for correction. Do NOT skip test files, do NOT mention them only in the Verification Plan.

INPUTS:
1. User Story (Requirements)
2. Governance Rules (Compliance constraints)
3. Role Instructions (Per-role detailed guidance)
4. ADRs (Codified architectural decisions)
5. Available Journeys Catalogue (Catalogue of all defined user workflows)
6. Available ADRs Catalogue (Catalogue of all architectural decisions)
7. Source File Tree (Repository structure)
8. Source Code Outlines (Imports, class/function signatures)

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

{preseeded_block}

GOVERNANCE RULES:
{rules_content}

DETAILED ROLE INSTRUCTIONS:
{instructions_content}

ARCHITECTURAL DECISIONS (ADRs):
{adrs_content}

{j_catalogue if j_catalogue else "No journeys defined."}

{a_catalogue if a_catalogue else "No ADRs defined."}

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

STORY FILE PATH (exact — use this verbatim for any runbook steps that reference this story):
{story_file.relative_to(story_file.parents[3])}

Generate the runbook now.
"""

    console.print("[bold green]🤖 Panel is discussing...[/bold green]")

    max_attempts = 3
    attempt = 0
    content = ""
    known_new_files: set = set()

    # Pre-populate from the story Impact Analysis [NEW] markers
    _ia_new = re.findall(
        r"-\s*`([^`]+)`\s*[—-]\s*\*\*\[NEW\]\*\*",
        story_content,
    )
    known_new_files.update(_ia_new)

    new_files_notice = (
        "\n\nFILES THAT DO NOT EXIST YET — use [NEW] not [MODIFY] for ALL of these:\n"
        + "\n".join(f"  - {f}" for f in sorted(known_new_files))
    ) if known_new_files else ""
    current_user_prompt = user_prompt + new_files_notice

    max_gate_corrections = 3
    gate_corrections = 0
    correction_parts: List[str] = []

    while attempt < max_attempts:
        attempt += 1
        try:
            with console.status(f"[bold green]🤖 Panel is discussing (Attempt {attempt}/{max_attempts})...[/bold green]") as status:
                content = ai_service.complete(system_prompt, current_user_prompt, rich_status=status)
        except TimeoutError as te:
            logger.error(
                "AI service timeout",
                extra={"story_id": story_id, "attempt": attempt},
                exc_info=te,
            )
            error_console.print(f"[bold red]❌ {te}[/bold red]")
            raise typer.Exit(code=1)

        if not content:
            logger.warning("ai_empty_response", extra={"story_id": story_id, "attempt": attempt})
            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt}: AI returned empty/malformed response — retrying...[/yellow]")
                continue
            else:
                console.print("[bold red]❌ AI returned empty response on final attempt.[/bold red]")
                raise typer.Exit(code=1)

        # -- SPLIT_REQUEST check --
        if "SPLIT_REQUEST" in content:
            if attempt == 1:
                break  # Let the split logic below handle it
            else:
                logger.warning(
                    "split_request_rejected_in_correction",
                    extra={"story_id": story_id, "attempt": attempt},
                )
                console.print(
                    f"[yellow]⚠️  Attempt {attempt}: AI tried to SPLIT_REQUEST inside a "
                    "correction loop — rejecting and retrying.[/yellow]"
                )
                if attempt < max_attempts:
                    current_user_prompt = (
                        f"{user_prompt}{new_files_notice}\n\n"
                        "=== CORRECTION REQUIRED ===\n"
                        "You responded with SPLIT_REQUEST, but you are in a correction loop. "
                        "You MUST generate the complete runbook. Do NOT emit SPLIT_REQUEST.\n\n"
                        "Previous correction instructions still apply:\n"
                        + "\n\n---\n\n".join(correction_parts)
                        + "\n\nReturn the FULL corrected runbook."
                    )
                    continue
                else:
                    logger.error("gate_exhausted", extra={"story_id": story_id, "attempt": attempt})
                    error_console.print(f"[bold red]❌ Gates failed after {max_attempts} attempts.[/bold red]")
                    raise typer.Exit(code=1)

        # ── Gate pass ──
        content, correction_parts, gate_corrections, known_new_files, attempt_delta = run_generation_gates(
            content=content,
            story_id=story_id,
            story_content=story_content,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            known_new_files=known_new_files,
            attempt=attempt,
            max_attempts=max_attempts,
            gate_corrections=gate_corrections,
            max_gate_corrections=max_gate_corrections,
        )
        attempt += attempt_delta

        # S/R targeted fix succeeded — re-run gates
        if correction_parts == ["__SR_PATCHED__"]:
            continue

        # Combined correction needed
        if correction_parts:
            if attempt < max_attempts:
                issues = len(correction_parts)
                console.print(f"[yellow]⚠️  Attempt {attempt}: {issues} gate issue(s) — sending combined correction...[/yellow]")
                logger.info("combined_correction_attempt", extra={"attempt": attempt, "story_id": story_id, "issues": issues})
                gate_corrections += 1
                if gate_corrections > max_gate_corrections:
                    logger.error("gate_corrections_exhausted", extra={"story_id": story_id, "gate_corrections": gate_corrections})
                    error_console.print(f"[bold red]❌ Gate corrections exhausted ({max_gate_corrections} corrections).[/bold red]")
                    for part in correction_parts:
                        error_console.print(f"[red]{part[:400]}[/red]")
                    raise typer.Exit(code=1)
                attempt -= 1
                new_files_notice = (
                    "\n\nFILES THAT DO NOT EXIST YET — use [NEW] not [MODIFY] for ALL of these:\n"
                    + "\n".join(f"  - {f}" for f in sorted(known_new_files))
                ) if known_new_files else ""
                current_user_prompt = (
                    f"{user_prompt}{new_files_notice}\n\n"
                    "=== CORRECTION REQUIRED ===\n"
                    "The runbook has the following issues that must be fixed:\n\n"
                    + "\n\n---\n\n".join(correction_parts)
                    + "\n\nIMPORTANT: Return the FULL corrected runbook with these issues fixed. "
                    "Preserve ALL existing valid content exactly as-is. Only modify the "
                    "specific sections listed above."
                )
                continue
            else:
                logger.error("gate_exhausted", extra={"story_id": story_id, "attempt": attempt})
                error_console.print(f"[bold red]❌ Gates failed after {max_attempts} attempts.[/bold red]")
                for part in correction_parts:
                    error_console.print(f"[red]{part[:400]}[/red]")
                raise typer.Exit(code=1)

        # Deterministic auto-fixes
        content = auto_fix_license_headers(content)
        content = auto_fix_changelog_step(content)

        # DoD gate
        content, dod_gaps, gate_corrections, patched = run_dod_gate(
            content=content,
            story_id=story_id,
            story_content=story_content,
            attempt=attempt,
            gate_corrections=gate_corrections,
            max_gate_corrections=max_gate_corrections,
        )

        if dod_gaps and patched:
            # Re-run DoD checks on the patched content
            attempt -= 1
            continue
        elif not dod_gaps:
            break

    # -- SPLIT_REQUEST Fallback (INFRA-094) --
    if "SPLIT_REQUEST" in content:
        split_data = parse_split_request(content)
        if split_data:
            config.split_requests_dir.mkdir(parents=True, exist_ok=True)
            split_path = config.split_requests_dir / f"{story_id}.json"
            split_path.write_text(json.dumps(split_data, indent=2))

            logger.warning(
                "split_request story=%s reason=%s suggestion_count=%d",
                story_id,
                scrub_sensitive_data(split_data.get("reason", ""))[:200],
                len(split_data.get("suggestions", [])),
            )

            if skip_forecast:
                logger.info(
                    "split_request advisory_only=True story=%s (--skip-forecast)",
                    story_id,
                )
                console.print(
                    "[dim]ℹ️  AI recommended splitting (advisory only — "
                    "--skip-forecast active). Generating runbook anyway.[/dim]"
                )
                console.print("[bold green]🤖 Panel is re-generating (no split directive)...[/bold green]")
                with console.status("[bold green]🤖 Panel is re-generating...[/bold green]") as status:
                    content = ai_service.complete(system_prompt, user_prompt, rich_status=status)
                if not content:
                    console.print("[bold red]❌ AI returned empty response on retry.[/bold red]")
                    raise typer.Exit(code=1)
            else:
                console.print("[bold yellow]⚠️  AI recommends splitting this story.[/bold yellow]")
                console.print(f"  • Reason: {split_data.get('reason', 'N/A')}")
                est_loc = split_data.get('estimated_loc')
                est_files = split_data.get('estimated_files')
                if est_loc or est_files:
                    console.print(f"  • Estimated scope: ~{est_loc or '?'} LOC across {est_files or '?'} files")
                console.print(f"  • Suggestions: {len(split_data.get('suggestions', []))}")
                for i, s in enumerate(split_data.get("suggestions", []), 1):
                    console.print(f"    {i}. {s}")
                console.print(f"\nDecomposition saved to: {split_path}")
                console.print("[dim]Create child stories with: agent new-story <ID>[/dim]")
                raise typer.Exit(code=2)

    return content
