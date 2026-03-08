# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0 (the "License");

import subprocess
from rich.console import Console
from rich.panel import Panel

def handle_blocked_findings(console: Console, result: dict, interactive: bool, story_id: str | None, config) -> bool:
    """Render findings and initiate interactive repair if enabled."""
    console.print("\n[bold red]⛔ Preflight Blocked by Governance Council:[/bold red]")
    console.print(f"\n[dim]Detailed report saved to: {result.get('log_file')}[/dim]")
     
    console.print("\n[bold]Governance Council Findings:[/bold]")

    # Categorize roles
    roles = result.get("json_report", {}).get("roles", [])
    passed_clean = []
    passed_with_findings = []
    blocking_roles = []

    for role in roles:
        name = role.get("name", "Unknown")
        verdict = role.get("verdict", "UNKNOWN")
        findings = role.get("findings", [])

        if verdict == "PASS":
            if not findings:
                passed_clean.append(name)
            else:
                passed_with_findings.append(name)
        else:
            blocking_roles.append(role)

    # 1. Summary of Clean Passes
    if passed_clean:
        console.print(f"[green]✅ Approved (No Issues): {', '.join(passed_clean)}[/green]")

    # 2. Summary of Passes with Findings (Suppressed Details)
    if passed_with_findings:
        console.print(f"[yellow]⚠️  Approved with Notes (Details Suppressed): {', '.join(passed_with_findings)}[/yellow]")

    # 3. Blocking Issues — single pass for both panels and interactive repair list
    blocking_findings = []
    if blocking_roles:
        blocking_names = [r.get("name", "Unknown") for r in blocking_roles]
        console.print(f"[bold red]❌ Blocking Issues: {', '.join(blocking_names)}[/bold red]")

        for role in blocking_roles:
            name = role.get("name", "Unknown")
            findings = role.get("findings", [])
            summary = role.get("summary", "")
            required_changes = role.get("required_changes", [])

            # Build structured panel content
            lines = []
            lines.append("VERDICT: BLOCK")
            if summary:
                lines.append("SUMMARY:")
                lines.append(f"{summary}")
            if findings:
                lines.append("FINDINGS:")
                for f in findings:
                    lines.append(f"- {f}")
                    blocking_findings.append(f"{name}: {f}")
            if required_changes:
                lines.append("REQUIRED_CHANGES:")
                for c in required_changes:
                    lines.append(f"- {c}")
            
            if not findings and not required_changes:
                lines.append("[dim]Blocking verdict but no specific findings provided.[/dim]")
            
            content = "\n".join(lines)
            console.print(Panel(content, title=f"❌ {name}", border_style="red"))

    # --- Interactive repair ---
    if interactive and blocking_findings:
        console.print("\n[bold yellow]🔧 Initiating Agentic Repair for Blocking Findings...[/bold yellow]")
        
        target_file_path = None
        if story_id:
            for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
                if file_path.name.startswith(story_id):
                    target_file_path = file_path
                    break
                    
        import asyncio
        from agent.tui.agentic import run_agentic_loop
        from agent.core.config import config as app_config
        from agent.core.ai import ai_service as app_ai_service
        
        system_prompt = (
            "You are an expert developer resolving preflight governance failures. "
            "You must read the findings, examine the story or codebase, formulate a solution, "
            "and apply it using your tools. Use `patch_file` or `edit_file` to fix issues. "
            "When you are done, describe what you fixed in your Final Answer."
        )
        
        context_str = f"Story ID: {story_id}\nTarget File: {target_file_path}\n\n" if target_file_path else ""
        user_prompt = f"Fix the following blocking findings:\n{context_str}" + "\n".join(blocking_findings)
        
        def on_thought(thought: str, step: int):
            console.print(f"[dim cyan]🤔 Thought:[/dim cyan] [dim]{thought.strip()}[/dim]")

        def on_tool_call(tool: str, args: dict, step: int):
            console.print(f"[dim magenta]🛠️  Action:[/dim magenta] [bold]{tool}[/bold] [dim]{args}[/dim]")
            
        try:
            console.print(f"[dim]Starting AgentExecutor loop...[/dim]")
            final_answer = asyncio.run(run_agentic_loop(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                messages=[],
                repo_root=app_config.repo_root,
                provider=app_ai_service.provider,
                model=app_ai_service.models.get(app_ai_service.provider),
                on_thought=on_thought,
                on_tool_call=on_tool_call,
            ))
            console.print(f"\n[bold green]✅ Repair Completed. Agent said:[/bold green]\n{final_answer}")
            
            # Re-stage all modified files
            subprocess.run(["git", "add", "-u"], capture_output=True, text=True)
            
            console.print("[bold cyan]🔄 Re-running governance checks to verify fix...[/bold cyan]")
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠️  Agentic repair failed: {e}[/yellow]")

    return False
