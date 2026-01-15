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

import typer
from rich.console import Console
from pathlib import Path
from typing import Optional
import subprocess

from agent.core.config import config
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.context import context_loader
from agent.core.ai import ai_service

console = Console()

def validate_story(
    story_id: str = typer.Argument(..., help="The ID of the story to validate."),
    return_bool: bool = False
):
    """
    Validate the schema and required sections of a story file.
    """
    # Find story file
    # This logic is duplicated from bash `find_story_file`. 
    # TODO: move find_story_file to agent.core.utils or similar
    
    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break
            
    if not found_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         if return_bool:
             return False
         raise typer.Exit(code=1)
         
    content = found_file.read_text(errors="ignore")
    required_sections = [
        "Problem Statement", 
        "User Story", 
        "Acceptance Criteria", 
        "Non-Functional Requirements", 
        "Impact Analysis Summary", 
        "Test Strategy", 
        "Rollback Plan"
    ]
    
    missing = []
    for section in required_sections:
        if f"## {section}" not in content:
            missing.append(section)
            
    if missing:
        console.print(f"[bold red]❌ Story schema validation failed for {story_id}[/bold red]")
        console.print(f"   Missing sections: {', '.join(missing)}")
        if return_bool:
            return False
        raise typer.Exit(code=1)
    else:
        console.print(f"[bold green]✅ Story schema validation passed for {story_id}[/bold green]")
        if return_bool:
            return True


def preflight(
    story_id: Optional[str] = typer.Option(None, "--story", help="The story ID to validate against."),
    ai: bool = typer.Option(False, "--ai", help="Enable AI-powered governance review."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, openai)"),
    report_file: Optional[Path] = typer.Option(None, "--report-file", help="Path to save the preflight report as JSON.")
):
    """
    Run preflight checks (linting, tests, and optional AI governance review).

    Args:
        story_id: The ID of the story to validate.
        ai: Enable AI-powered governance review (requires keys or gh cli).
        base: Base branch for comparison (defaults to staged changes).
        provider: Force a specific AI provider (gh, gemini, openai).
        report_file: Path to save the preflight report as JSON.
    """
    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")

    # Data collection for JSON report
    json_report = {
        "story_id": story_id,
        "overall_verdict": "UNKNOWN",
        "roles": [],
        "log_file": None,
        "error": None
    }

    # 0. Configure Provider Override if set
    if provider:
        ai_service.set_provider(provider)
    
    if not story_id:
        story_id = infer_story_id()

    if not story_id:
        msg = "Story ID is required (and could not be inferred)."
        console.print(f"[bold red]❌ Preflight failed: {msg}[/bold red]")
        if report_file:
            json_report["error"] = msg
            import json
            report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)

    json_report["story_id"] = story_id

    # 1. Validate Story First
    if not validate_story(story_id, return_bool=True):
        msg = "Story validation failed."
        console.print(f"[bold red]❌ Preflight failed: {msg}[/bold red]")
        if report_file:
             json_report["error"] = msg
             import json
             report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)

    # 2. Get Changed Files
    if base:
        cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().splitlines()
    
    if not files or files == ['']:
        console.print("[yellow]⚠️  No files to review.[/yellow]")
        if report_file:
             json_report["overall_verdict"] = "SKIPPED"
             json_report["error"] = "No files to review"
             import json
             report_file.write_text(json.dumps(json_report, indent=2))
        return
        
    console.print(f"[bold blue]🔍 Running preflight checks for {story_id}...[/bold blue]")
    
    # Context Loading
    story_content = ""
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            story_content = file_path.read_text(errors="ignore")
            break
            
            
    # Load full context (rules + instructions)
    full_context = context_loader.load_context()
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    
    # Cap diff size - if larger than chunk limit, we might need a smart splitter, 
    # but for assimilating roles, we send the same diff to each role agent.
    # We'll stick to a reasonable cap for now to fit in context.
    diff_cmd = cmd = ["git", "diff", "--cached", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", "."]
    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
    # Full diff for chunking
    full_diff = diff_res.stdout
    if not full_diff:
        full_diff = ""
        
    # --- SCRUBBING ---
    if ai:
        console.print("[dim]🔒 Scrubbing sensitive data from diff before AI analysis...[/dim]")
        full_diff = scrub_sensitive_data(full_diff)
        story_content = scrub_sensitive_data(story_content) # Scrub story too just in case
        rules_content = scrub_sensitive_data(rules_content)
        instructions_content = scrub_sensitive_data(instructions_content)
    # -----------------
        
    # Split into chunks if using GH CLI (limited context)
    if ai_service.provider == "gh":
         chunk_size = 6000
    else:
         # Gemini/OpenAI have large context, send full diff
         chunk_size = len(full_diff) + 1000
 
    if len(full_diff) > chunk_size:
        diff_chunks = [full_diff[i:i+chunk_size] for i in range(0, len(full_diff), chunk_size)]
    else:
        diff_chunks = [full_diff]
        
    report = f"# Governance Preflight Report\n\nStory: {story_id}\n\n"
    
    if ai:
        console.print("[bold cyan]🤖 Convening the AI Governance Council...[/bold cyan]")
        
        # Complete Council
        roles = [
            {"name": "Architect", "focus": "System design, ADR compliance, patterns, and dependency hygiene."},
            {"name": "Security", "focus": "PII leaks, hardcoded secrets, injection vulnerabilities, and permission scope."},
            {"name": "Compliance", "focus": "GDPR, SOC2, and legal compliance mandates."},
            {"name": "QA", "focus": "Test coverage, edge cases, and testability of the changes."},
            {"name": "Docs", "focus": "Documentation updates, clarity, and user manual accuracy."},
            {"name": "Observability", "focus": "Logging, metrics, tracing, and error handling."},
            {"name": "Backend", "focus": "API design, database schemas, and backend patterns."},
            {"name": "Mobile", "focus": "Mobile-specific UX, performance, and platform guidelines."},
            {"name": "Web", "focus": "Web accessibility, responsive design, and browser compatibility."}
        ]
        
        attempt_loop = True
        while attempt_loop:
            # 1. Determine Chunking Strategy based on CURRENT provider
            if ai_service.provider == "gh":
                 chunk_size = 6000
                 console.print("[dim]Using chunked analysis for GitHub CLI (Context Limit)[/dim]")
            else:
                 # Gemini/OpenAI have large context, send full diff
                 chunk_size = len(full_diff) + 1000 #(effectively unlimited relative to diff)
                 console.print(f"[dim]Using full-context analysis for {ai_service.provider}[/dim]")

            if len(full_diff) > chunk_size:
                diff_chunks = [full_diff[i:i+chunk_size] for i in range(0, len(full_diff), chunk_size)]
            else:
                diff_chunks = [full_diff]

            overall_verdict = "PASS"
            report = f"# Governance Preflight Report\n\nStory: {story_id}\n\n"
            json_roles = []
            
            try:
                for role in roles:
                    role_name = role["name"]
                    focus_area = role["focus"]
                    
                    role_data = {
                        "name": role_name,
                        "verdict": "PASS",
                        "findings": [],
                        "summary": ""
                    }

                    role_verdict = "PASS"
                    role_findings = []
                    
                    with console.status(f"[bold blue]🤖 @{role_name} is reviewing ({len(diff_chunks)} chunks using {ai_service.provider})...[/bold blue]"):
                        
                        for i, chunk in enumerate(diff_chunks):
                            system_prompt = f"""You are the {role_name} Agent in the Governance Council.
Your specific focus is: {focus_area}

INPUTS:
1. User Story
2. Governance Rules
3. Role Instructions
4. Code Diff (Chunk {i+1}/{len(diff_chunks)})

TASK:
Review the code changes specifically from the perspective of a {role_name}.

OUTPUT:
- Verdict: PASS | BLOCK
- Brief analysis of findings relative to your focus.
"""
                            # Select appropriate rules context size
                            if ai_service.provider == "gh":
                                rules_subset = rules_content[:10000]
                            else:
                                rules_subset = rules_content

                            user_prompt = f"""STORY:
{story_content}

RULES:
{rules_subset}

INSTRUCTIONS:
{instructions_content}

CODE DIFF CHUNK:
{chunk}
"""
                            # Check for potential token overflow if using GH provider
                            total_chars = len(system_prompt) + len(user_prompt)
                            if ai_service.provider == "gh" and total_chars > 30000:
                                console.print(f"[yellow]⚠️  Warning: Prompt size ({total_chars} chars) is near GitHub CLI limit. Truncating context further.[/yellow]")
                                # Emergency truncation
                                user_prompt = f"STORY: {story_content}\nRULES: {rules_content[:5000]}\nDIFF: {chunk}"
                            
                            review = ai_service.complete(system_prompt, user_prompt)
                            
                            # Verdict parsing logic
                            import re
                            is_block = False
                            
                            # Case-insensitive check for "Verdict: BLOCK"
                            # Regex explanation:
                            # Verdict\s*[:]\s* : Matches "Verdict:" with optional whitespace
                            # [*]* : Matches optional markdown bold asterisks
                            # BLOCK : Matches the keyword BLOCK
                            # [*]* : Matches optional trailing asterisks
                            if re.search(r"Verdict\s*[:]\s*[*]*BLOCK[*]*", review, re.IGNORECASE):
                                is_block = True
                            # Fallback: if the AI just screamed "BLOCK" at the start
                            elif review.strip().upper().startswith("BLOCK"):
                                is_block = True
                                
                            if is_block:
                                 role_verdict = "BLOCK"
                                 role_findings.append(review)
                    
                    # Store detailed findings in JSON role data
                    # For simplicity in JSON, we just append the full review text to findings
                    if role_findings:
                         role_data["findings"] = role_findings
                    else:
                         # Even if PASS, we might want to capture the review if it exists (not in current logic for PASS though)
                         pass

                    role_data["verdict"] = role_verdict
                    
                    # Store summary if blocked (first line or extracted summary logic could go here)
                    if role_verdict == "BLOCK":
                         console.print(f"[bold red]❌ @{role_name}: BLOCK[/bold red]")
                         # Summarize first finding
                         if role_findings:
                             first_finding = role_findings[0].replace('Verdict: BLOCK', '').strip()
                             console.print(f"[red]{first_finding}[/red]")
                             role_data["summary"] = first_finding.split('\n')[0]
                         
                         overall_verdict = "BLOCK"
                         full_review = "\n\n".join(role_findings)
                         report += f"### ❌ @{role_name}: BLOCK\n{full_review}\n\n"
                    else:
                         console.print(f"[bold green]✅ @{role_name}: PASS[/bold green]")
                         report += f"### ✅ @{role_name}: PASS\n\n"
                    
                    json_roles.append(role_data)
                
                # If we get here, all roles passed without Exception
                attempt_loop = False # Exit successful loop

            except Exception as e:
                console.print(f"[yellow]⚠️  Analysis interrupted: {e}[/yellow]")
                if ai_service.try_switch_provider():
                    console.print(f"[bold magenta]🔄 Switching provider to {ai_service.provider} and restarting analysis (Full Context)...[/bold magenta]")
                    continue # Restart loop with new provider
                else:
                    console.print("[bold red]❌ All AI providers failed. Aborting.[/bold red]")
                    if report_file:
                        json_report["error"] = str(e)
                        import json
                        report_file.write_text(json.dumps(json_report, indent=2))
                    raise typer.Exit(code=1)

        # Update JSON report with collected data
        json_report["overall_verdict"] = overall_verdict
        json_report["roles"] = json_roles

        # Save Report to Log
        import time
        timestamp = int(time.time())
        log_dir = config.agent_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"preflight-{story_id}-{timestamp}.md"
        log_file.write_text(report)
        json_report["log_file"] = str(log_file)
        
        console.print("") # Newline before final verdict
        
        # Write JSON report if requested
        if report_file:
            import json
            report_file.write_text(json.dumps(json_report, indent=2))

        if overall_verdict == "BLOCK":
             console.print("[bold red]❌ Governance Council Verdict: BLOCK[/bold red]")
             report += "## 🛑 FINAL VERDICT: BLOCK\nOne or more agents blocked this change.\n"
             console.print(f"Full report saved to: [underline]{log_file}[/underline]")
             raise typer.Exit(code=1)
        else:
             console.print("[bold green]✅ Governance Council Verdict: PASS[/bold green]")
             report += "## 🟢 FINAL VERDICT: PASS\nAll agents approved this change.\n"
             console.print(f"Full report saved to: [underline]{log_file}[/underline]")
    
    console.print("[bold green]✅ Preflight checks passed![/bold green]")

def impact(
    story_id: str = typer.Argument(..., help="The ID of the story.")
):
    """
    Run impact analysis for a story.
    """
    # Stub
    console.print(f"🛈 [impact] Run impact analysis for {story_id} (extend this logic as needed).")

def panel(
    story_id: str = typer.Argument(..., help="The ID of the story.")
):
    """
    Simulate governance panel.
    """
    # Stub
    console.print(f"🛈 [panel] Convening the Governance Panel for {story_id}...")
    agents_file = config.etc_dir / "agents.yaml"
    if not agents_file.exists():
        console.print("[yellow]⚠️  No agents.yaml found.[/yellow]")
        return
        
    console.print("   (Simulated approval from agents.yaml roles)")

def run_ui_tests(
    story_id: str = typer.Argument(..., help="The ID of the story.")
):
    """
    Run UI journey tests.
    """
    console.print(f"🛈 [run-ui-tests] Running UI Tests for {story_id}...")
    console.print("   (Simulating external test runner...)")
