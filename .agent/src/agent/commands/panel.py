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

import re
import subprocess
import time
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from opentelemetry import trace

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from agent.core.logger import get_logger
from agent.core.config import config
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.governance import convene_council_full
from agent.core.check.reporting import print_reference_summary as _print_reference_summary
from agent.core.context import context_loader
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.utils.validation_formatter import format_runbook_errors

console = Console()
error_console = Console(stderr=True)
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

def panel(
    input_arg: Optional[str] = typer.Argument(None, help="Story ID OR a question/instruction for the panel."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."),
    apply: bool = typer.Option(False, "--apply", help="Apply the AI's advice directly to the file. For runbooks, schema is validated before writing. Use with caution."),
    panel_engine: Optional[str] = typer.Option(None, "--panel-engine", help="Override panel engine: 'adk' or 'native'.")
):
    """
    Convening the Governance Panel to review changes or discuss design.
    """
    from agent.core.ai import ai_service

    # 0. Configure Panel Engine Override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    # 1. Configure Provider Override if set
    if provider:
        ai_service.set_provider(provider)
    
    # Smart Argument Parsing
    story_id = None
    question = None
    
    if input_arg:
        # Check if input looks like a simple Story ID (e.g. "INFRA-123", "WEB-001")
        if re.match(r"^[A-Z]+-\d+$", input_arg.strip(), re.IGNORECASE):
            story_id = input_arg.upper()
        else:
            # Assume it's a question/instruction
            question = input_arg
            # Try to extract ID from question
            match = re.search(r"([A-Z]+-\d+)", input_arg, re.IGNORECASE)
            if match:
                story_id = match.group(1).upper()

    if not story_id:
        story_id = infer_story_id()
        if not story_id:
             # If we have a question but no story ID, maybe we can proceed?
             # But the tool relies on Story/Runbook context. 
             # Let's prompt or error.
             if question:
                 console.print(f"[yellow]⚠️  Could not identify a linked Story ID from '{question}'.[/yellow]")
             else:
                 console.print("[bold red]❌ Story ID is required (and could not be inferred).[/bold red]")
                 raise typer.Exit(code=1)

    console.print(f"[bold cyan]🤖 Convening the Governance Panel for {story_id}...[/bold cyan]")
    if question:
        console.print(f"[dim]❓ Question: {question}[/dim]")

    # 1. Get Changed Files
    if base:
        cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().splitlines()
    files = [f for f in files if f] # Filter empty strings
    
    if not files:
        console.print("[yellow]⚠️  No staged changes found. Proceeding in Design Review mode (Document Context Only).[/yellow]")

    # 2. Get Full Diff
    diff_cmd = ["git", "diff", "--cached", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", "."]
    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
    full_diff = diff_res.stdout
    if not full_diff:
        full_diff = ""

    # 3. Load Context & Target File
    story_content = ""
    target_file = None
    
    # Try finding Runbook first (priority for implementation phase)
    # Check common locations or use basic glob
    for file_path in config.runbooks_dir.rglob(f"{story_id}*.md"):
        if story_id in file_path.name:
            target_file = file_path
            story_content = file_path.read_text(errors="ignore")
            console.print(f"[dim]📄 Found Runbook: {file_path.name}[/dim]")
            break
            
    # Fallback to Story
    if not target_file:
        for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
            if file_path.name.startswith(story_id):
                target_file = file_path
                story_content = file_path.read_text(errors="ignore")
                console.print(f"[dim]📄 Found Story: {file_path.name}[/dim]")
                break
    
    if not story_content:
         console.print(f"[yellow]⚠️  Story/Runbook for {story_id} not found. Reviewing without specific document context.[/yellow]")

    import asyncio
    full_context = asyncio.run(context_loader.load_context(story_id=story_id))
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    adrs_content = full_context.get("adrs", "")
    
    # 4. Scrum & Run
    full_diff = scrub_sensitive_data(full_diff)
    scrubbed_content = scrub_sensitive_data(story_content)
    rules_content = scrub_sensitive_data(rules_content)
    instructions_content = scrub_sensitive_data(instructions_content)


    console.print("[bold cyan]🤖 Convening AI Governance Panel (Consultation)...[/bold cyan]")
    with console.status("[bold cyan]🤖 Convening AI Governance Panel (Consultation)...[/bold cyan]"):
        try:
            result = convene_council_full(
                story_id=story_id,
                story_content=scrubbed_content,
                rules_content=rules_content,
                instructions_content=instructions_content,
                full_diff=full_diff,
                mode="consultative",
                council_identifier="panel",
                user_question=question,
                adrs_content=adrs_content,
                progress_callback=None # Silence individual role progress
            )
        except Exception as e:
            console.print(f"\n[bold red]❌ Governance Panel Failed:[/bold red] {e}")
            if any(ind in str(e).lower() for ind in ["ssl", "certificate_verify", "deadline_exceeded", "504", "deadline expired"]):
                console.print("[yellow]Hint: Your corporate proxy may be blocking the AI provider or hitting API rate limits/timeouts. Check your VPN/Proxy settings.[/yellow]")
            raise typer.Exit(code=1)
    
    # 4.5 Display Results
    console.print("\n[bold]Governance Panel Findings:[/bold]")

    roles = result.get("json_report", {}).get("roles", [])
    silent_roles = []
    active_roles = []
    
    for role in roles:
        findings = role.get("findings", [])
        if not findings:
            silent_roles.append(role.get("name", "Unknown"))
        else:
            active_roles.append(role)
            
    if silent_roles:
        console.print(f"[dim]ℹ️  No advice from: {', '.join(silent_roles)}[/dim]")
        
    for role in active_roles:
        name = role.get("name", "Unknown")
        findings = role.get("findings", [])
        
        # In Consultative mode, findings are usually the full advice
        content = ""
        if isinstance(findings, list):
            content = "\n".join(findings)
        else:
            content = str(findings)
            
        console.print(Panel(content, title=f"🤖 {name}", border_style="blue"))

    # Display Reference Summary Table (INFRA-060 AC-9)
    _ref_metrics = result.get("json_report", {}).get("reference_metrics", {})
    _roles_data = result.get("json_report", {}).get("roles", [])
    _fv_metrics = result.get("json_report", {}).get("finding_validation", {})
    if _ref_metrics.get("total_refs", 0) > 0 or _roles_data:
        _print_reference_summary(console, _roles_data, _ref_metrics, _fv_metrics)

    # 5. Apply Advice
    if apply and target_file and result["log_file"]:
        console.print(f"\n[bold magenta]🏗️  Applying advice to {target_file.name}...[/bold magenta]")
        
        log_path = result["log_file"]
        report_text = log_path.read_text()
        
        prompt = f"""You are an Expert Technical Writer and Architect.
        
TASK:
Update the following document based on the advice from the Governance Panel.
Appy the advice intelligently. Do not just append it. Integrate it into the relevant sections.
If the advice suggests changes to code, do NOT change code, but update the plan/spec to reflect the need for changes.
Maintain the original document structure/headers.

DOCUMENT ({target_file.name}):
{story_content}

GOVERNANCE ADVICE:
{report_text}

OUTPUT:
Return ONLY the full updated markdown content of the document.
"""
        updated_content = ai_service.get_completion(prompt)
        
        # Clean up markdown formatting if present (strip code blocks)
        if updated_content:
            content = updated_content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                # Remove first line if it's a code block start
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                # Remove last line if it's a code block end
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                updated_content = "\n".join(lines).strip()
        
        # Safety check: ensure content is not empty
        if updated_content and len(updated_content) > 100:
            # INFRA-149: Schema validation for runbooks before applying
            if "runbook" in target_file.name.lower():
                with tracer.start_as_current_span("validate_runbook_schema") as span:
                    violations = validate_runbook_schema(updated_content)
                    span.set_attribute("validation.passed", not bool(violations))
                    span.set_attribute("validation.error_count", len(violations) if violations else 0)
                if violations:
                    logger.warning(
                        "panel_apply_validation_failed",
                        extra={
                            "file": target_file.name,
                            "error_count": len(violations),
                            "violations": violations,
                        },
                    )
                    error_console.print(f"[bold red]❌ Validation failed for {target_file.name}:[/bold red]")
                    error_console.print(format_runbook_errors(violations))
                    error_console.print("[yellow]Aborting apply to prevent file corruption.[/yellow]")
                    raise typer.Exit(code=1)
            
            target_file.write_text(updated_content)
            console.print(f"[bold green]✅ Applied advice to {target_file.name}[/bold green]")
        else:
             console.print("[bold red]❌ Failed to generate valid update (Content empty or too short).[/bold red]")
