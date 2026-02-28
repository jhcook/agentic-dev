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

import subprocess
import time
from typing import Optional

import typer
from rich.console import Console

from agent.commands.check import preflight  # Verify import works or move core logic
from agent.core.utils import infer_story_id
from agent.core.auth.credentials import validate_credentials

console = Console()

# Helper functions moved to agent.core.utils

def pr(
    story_id: Optional[str] = typer.Option(None, "--story", help="Story ID."),
    web: bool = typer.Option(False, "--web", help="Open PR in browser."),
    draft: bool = typer.Option(False, "--draft", help="Create draft PR."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input for PR summary."),
    skip_preflight: bool = typer.Option(False, "--skip-preflight", help="Skip preflight checks (audit-logged)."),
):
    """
    Open a GitHub Pull Request for the current branch.
    """
    if not story_id:
        story_id = infer_story_id()
        
    target_branch = "main"
    
    preflight_passed = True
    if skip_preflight:
        console.print(f"[yellow]⚠️  Preflight SKIPPED at {time.strftime('%Y-%m-%dT%H:%M:%S')} (--skip-preflight)[/yellow]")
        preflight_passed = False
    elif story_id:
        console.print(f"[bold blue]🕵️ Running preflight checks for {story_id} (against {target_branch})...[/bold blue]")
        try:
             preflight(
                 story_id=story_id, 
                 base=target_branch, 
                 offline=True, 
                 provider=provider, 
                 report_file=None,
                 skip_tests=False,
                 ignore_tests=False
             )
        except typer.Exit as e:
            if e.exit_code != 0:
                console.print("[bold red]❌ Preflight failed. Aborting PR creation.[/bold red]")
                raise typer.Exit(code=1)
    else:
        console.print("[yellow]⚠️  Skipping preflight (no Story ID).[/yellow]")
        preflight_passed = False

    console.print("🚀 Creating Pull Request...")
    
    commit_msg = subprocess.check_output(["git", "log", "-1", "--pretty=%s"]).decode().strip()
    title = commit_msg
    
    if story_id and story_id not in title:
        title = f"[{story_id}] {title}"
        
    gov_status = "✅ Preflight Passed" if preflight_passed else "⚠️ Preflight Skipped"
    tpl = "### Story Link\n{story_link}\n\n### Changes\n- {summary}\n\n### Governance Checks\n" + gov_status
    
    story_link = "N/A"
    if story_id:
        from agent.core.config import config
        # Attempt to find the story file
        matches = list(config.stories_dir.rglob(f"*{story_id}*.md"))
        if matches:
            # Use relative path for linking
            rel_path = matches[0].relative_to(config.repo_root)
            story_link = f"[{story_id}]({rel_path})"
        else:
            story_link = story_id

    summary = commit_msg
    if offline:
        content = typer.edit(text=commit_msg)
        if content:
            summary = content.strip()
    else:
        validate_credentials(check_llm=True)
        console.print("[dim]🤖 AI is generating a PR summary...[/dim]")
        try:
             # Get diff compared to main
             diff_content = subprocess.check_output(["git", "diff", f"{target_branch}...HEAD"], text=True)
             if diff_content:
                 from agent.core.ai import ai_service  # ADR-025: lazy init
                 from agent.core.utils import scrub_sensitive_data
                 
                 # Initialize provider if specified
                 if provider:
                     ai_service.set_provider(provider)
                     
                 scrubbed_diff = scrub_sensitive_data(diff_content)
                 
                 sys_prompt = "You are a senior developer. Generate a concise, high-level summary of the changes in this PR using bullet points. Focus on technical impact and key features. Use Markdown."
                 user_prompt = f"STORY ID: {story_id}\n\nDIFF:\n{scrubbed_diff[:8000]}" # Cap context
                 
                 generated = ai_service.complete(sys_prompt, user_prompt)
                 if generated:
                     summary = generated.strip()
        except Exception:
             console.print("[yellow]⚠️  AI PR summary generation failed (offline or error). Falling back to manual input.[/yellow]")
             content = typer.edit(text=commit_msg)
             if content:
                 summary = content.strip()

    from agent.core.utils import scrub_sensitive_data
    body = tpl.format(
        story_link=story_link,
        summary=summary
    )
    body = scrub_sensitive_data(body)
    
    gh_args = ["gh", "pr", "create", "--title", title, "--body", body, "--base", target_branch]
    if web:
        gh_args.append("--web")
    elif draft:
        gh_args.append("--draft")
    
    try:
        subprocess.run(gh_args, check=True)
    except subprocess.CalledProcessError:
        console.print("[bold red]❌ Failed to create PR.[/bold red]")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[bold red]❌ 'gh' CLI not found. Please install GitHub CLI.[/bold red]")
        raise typer.Exit(code=1)


def commit(
    story_id: Optional[str] = typer.Option(None, "--story", help="Story ID."),
    runbook_id: Optional[str] = typer.Option(None, "--runbook", help="Runbook ID."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message."),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input for commit message."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation/editing.")
):
    """
    Commit changes with a governed message.
    """
    # Configure AI if requested
    if not offline and provider:
        validate_credentials(check_llm=True)
        from agent.core.ai import ai_service  # ADR-025: lazy init
        ai_service.set_provider(provider)
    elif not offline: 
        validate_credentials(check_llm=True)
        # Ensure ai_service init is triggered if not explicitly imported at top level
        from agent.core.ai import ai_service  # ADR-025: lazy init

    # 1. Infer Story ID
    if not story_id:
        story_id = infer_story_id()
        
    if not story_id and not offline:
        console.print("[dim]🤖 AI is attempting to infer Story ID from changed files...[/dim]")
        # Get changed files
        try:
            diff_names = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).strip()
            if diff_names:
                from agent.core.utils import find_best_matching_story
                inferred = find_best_matching_story(diff_names)
                if inferred:
                    if typer.confirm(f"AI suggests story: [bold cyan]{inferred}[/bold cyan]. Use this?", default=True):
                        story_id = inferred
            else:
                console.print("[yellow]⚠️  No staged changes found to infer context from.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  AI inference failed: {e}[/yellow]")

    if not story_id:
         console.print("[bold red]❌ Story ID is required to commit.[/bold red]")
         raise typer.Exit(code=1)
         
    # 2. Generate or Ask for Message
    is_interactive = message is None

    if not message and not offline:
        console.print("[dim]🤖 AI is generating a commit message...[/dim]")
        try:
             diff_content = subprocess.check_output(["git", "diff", "--cached"], text=True)
             if diff_content:
                 from agent.core.ai import ai_service  # ADR-025: lazy init
                 from agent.core.utils import scrub_sensitive_data
                 
                 scrubbed_diff = scrub_sensitive_data(diff_content)
                 
                 sys_prompt = "You are a senior developer. Generate a concise, conventional commit message (max 72 chars subject) based on the diff."
                 user_prompt = f"STORY ID: {story_id}\n\nDIFF:\n{scrubbed_diff[:5000]}" # Cap context
                 
                 generated = ai_service.complete(sys_prompt, user_prompt)
                 if generated:
                     message = generated.strip().strip('"').strip("'")
        except Exception:
             console.print("[yellow]⚠️  AI commit message generation failed. Falling back to manual input.[/yellow]")

    if is_interactive and not yes:
        message = typer.edit(text=message or "")
        if message:
            message = message.strip()
    
    if not message:
         console.print("[bold red]❌ Commit message is required.[/bold red]")
         raise typer.Exit(code=1)
        
    full_message = f"[{story_id}] {message}"
    
    if runbook_id:
        full_message += f"\n\nRunbook: {runbook_id}"
        
    subprocess.run(["git", "commit", "-m", full_message])
    
    # Update Story State to COMMITTED
    from agent.commands.utils import update_story_state
    update_story_state(story_id, "COMMITTED", context_prefix="Post-Commit")
