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
Core governance logic for the Agent CLI.

This module provides the functionality for convening the AI Governance Council,
loading agent roles from configuration, and conducting preflight checks in both
gatekeeper and consultative modes.
"""


import re
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
import time

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.utils import scrub_sensitive_data

def load_roles() -> List[Dict[str, str]]:
    """
    Load roles from agents.yaml.
    Fallback to hardcoded roles if file is missing or invalid.
    """
    agents_file = config.etc_dir / "agents.yaml"
    roles = []
    
    if agents_file.exists():
        try:
            with open(agents_file, 'r') as f:
                data = yaml.safe_load(f)
                team = data.get('team', [])
                for member in team:
                    name = member.get('name', 'Unknown')
                    # Map 'role' to simple ID if needed, but 'name' is used in prompt
                    desc = member.get('description', '')
                    resps = member.get('responsibilities', [])
                    
                    # Construct 'focus' from description and responsibilities
                    focus = desc
                    if resps:
                        focus += f" Priorities: {', '.join(resps)}."
                        
                    roles.append({
                        "name": name,
                        "focus": focus,
                        "instruction": member.get('instruction', '') # specific instructions if any
                    })
        except Exception as e:
            # Fallback will handle this effectively, or we can log warning
            pass

    if not roles:
        # Fallback to defaults if loading failed
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
        
    return roles

def convene_council(
    console: Console,
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    diff_chunks: List[str],
    report_file: Optional[Path] = None
) -> str:
    """
    Run the AI Governance Council review on the provided diff chunks.
    Returns the overall verdict ("PASS" or "BLOCK").
    """
    console.print("[bold cyan]🤖 Convening the AI Governance Council...[/bold cyan]")
    
    roles = load_roles()
    
    # Determine chunking strategy for display
    # (Actual chunking logic happened before calling this, but we can re-verify or just handle what we have)
    # We trust caller provided valid chunks for the provider
    
    overall_verdict = "PASS"
    report = f"# Governance Preflight Report\n\nStory: {story_id}\n\n"
    json_roles = []
    
    attempt_loop = True
    while attempt_loop:
        # If we need to re-chunk because of provider switch, we might have an issue since we pass chunks in.
        # Ideally, this function handles the switching and re-chunking if it owns the diff.
        # For refactoring simplicity, we'll assume chunks are valid for current provider, 
        # OR we should pass the FULL diff and let 'convene_council' handle chunking.
        # Let's assume chunks passed are valid for current ai_service.provider. (Caller handles this).
        # Wait, if we switch provider inside here (exception catch), we need to re-chunk.
        # So we should pass 'full_diff' and let this function chunk.
        pass 
        # Making a design decision: Caller passes full diff strings, this function chunks.
        break # Breaking hypothetical loop to proceed with implementation

    return "PASS" # Stub for the moment while I decide on signature

def convene_council_full(
    console: Console,
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    report_file: Optional[Path] = None,
    mode: str = "gatekeeper" # gatekeeper | consultative
) -> str:
    """
    Run the AI Governance Council review. Handles provider switching and re-chunking.
    """
    console.print("[bold cyan]🤖 Convening the AI Governance Council...[/bold cyan]")
    
    roles = load_roles()

    json_report = {
        "story_id": story_id,
        "overall_verdict": "UNKNOWN",
        "roles": [],
        "log_file": None,
        "error": None
    }
    
    attempt_loop = True
    while attempt_loop:
        # 1. Determine Chunking Strategy
        if ai_service.provider == "gh":
                chunk_size = 6000
                console.print("[dim]Using chunked analysis for GitHub CLI (Context Limit)[/dim]")
        else:
                chunk_size = len(full_diff) + 1000 
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
                focus_area = role.get("focus", role.get("description", ""))
                
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
                        if mode == "consultative":
                            system_prompt = f"""You are the {role_name} Agent in the Governance Council.
Your specific focus is: {focus_area}

INPUTS:
1. User Story
2. Governance Rules
3. Role Instructions
4. Code Diff (Chunk {i+1}/{len(diff_chunks)})

TASK:
Provide expert consultation on the changes.
Do NOT act as a gatekeeper. Provide HELPFUL ADVICE.

OUTPUT:
- Sentiment: POSITIVE | NEUTRAL | NEGATIVE
- Advice: Specific, actionable, forward-looking advice.
- Deep Dive: (Optional) Technical details.
"""
                        else:
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
                        total_chars = len(system_prompt) + len(user_prompt)
                        if ai_service.provider == "gh" and total_chars > 30000:
                             console.print(f"[yellow]⚠️  Warning: Prompt size ({total_chars} chars) is near GitHub CLI limit. Truncating context further.[/yellow]")
                             user_prompt = f"STORY: {story_content}\nRULES: {rules_content[:5000]}\nDIFF: {chunk}"
                        
                        review = ai_service.complete(system_prompt, user_prompt)
                        
                        if mode == "consultative":
                             role_findings.append(review)
                             # No blocking concept in consulatative mode
                        else:
                            # Verdict parsing logic
                            is_block = False
                            if re.search(r"Verdict\s*[:]\s*[*]*BLOCK[*]*", review, re.IGNORECASE):
                                is_block = True
                            elif review.strip().upper().startswith("BLOCK"):
                                is_block = True
                                
                            if is_block:
                                    role_verdict = "BLOCK"
                                    role_findings.append(review)
                
                if role_findings:
                        role_data["findings"] = role_findings
                
                role_data["verdict"] = role_verdict
                
                if mode == "consultative":
                     console.print(f"[bold cyan]ℹ️  @{role_name}: CONSULTED[/bold cyan]")
                     report += f"### ℹ️ @{role_name}: ADVICE\n\n"
                     # Add summary of advice
                     if role_findings:
                         full_review = "\n\n".join(role_findings)
                         console.print(f"[dim]{full_review.splitlines()[0]}[/dim]") # Print first line
                         report += f"{full_review}\n\n"

                elif role_verdict == "BLOCK":
                        console.print(f"[bold red]❌ @{role_name}: BLOCK[/bold red]")
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
            
            attempt_loop = False 

        except Exception as e:
            console.print(f"[yellow]⚠️  Analysis interrupted: {e}[/yellow]")
            if ai_service.try_switch_provider():
                console.print(f"[bold magenta]🔄 Switching provider to {ai_service.provider} and restarting analysis (Full Context)...[/bold magenta]")
                continue
            else:
                console.print("[bold red]❌ All AI providers failed. Aborting.[/bold red]")
                if report_file:
                    json_report["error"] = str(e)
                    import json
                    report_file.write_text(json.dumps(json_report, indent=2))
                return "FAIL" # Or raise exception

    # Update JSON report
    json_report["overall_verdict"] = overall_verdict
    json_report["roles"] = json_roles

    # Save Log
    timestamp = int(time.time())
    log_dir = config.agent_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True) # ensure exists
    log_file = log_dir / f"governance-{story_id}-{timestamp}.md"
    log_file.write_text(report)
    json_report["log_file"] = str(log_file)
    
    console.print("")
    
    if report_file:
        import json
        report_file.write_text(json.dumps(json_report, indent=2))

    if overall_verdict == "BLOCK" and mode == "gatekeeper":
            console.print("[bold red]❌ Governance Council Verdict: BLOCK[/bold red]")
            report += "## 🛑 FINAL VERDICT: BLOCK\nOne or more agents blocked this change.\n"
            console.print(f"Full report saved to: [underline]{log_file}[/underline]")
    elif mode == "consultative":
            console.print("[bold cyan]ℹ️  Governance Council Consultation Complete[/bold cyan]")
            report += "## ℹ️ FINAL: CONSULTATION COMPLETE\nSee advice above.\n"
            console.print(f"Full report saved to: [underline]{log_file}[/underline]")
    else:
            console.print("[bold green]✅ Governance Council Verdict: PASS[/bold green]")
            report += "## 🟢 FINAL VERDICT: PASS\nAll agents approved this change.\n"
            console.print(f"Full report saved to: [underline]{log_file}[/underline]")
            
    return overall_verdict
