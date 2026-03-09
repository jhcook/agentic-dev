# Copyright 2026 Justin Cook
from typing import Optional

import typer
from rich.console import Console

from agent.core.logger import get_logger

console = Console()
logger = get_logger(__name__)

def impact(
    story_id: str = typer.Argument(..., help="The ID of the story."),
    offline: bool = typer.Option(False, "--offline", help="Disable AI-powered impact analysis."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    update_story: bool = typer.Option(False, "--update-story", help="Update the story file with the impact analysis."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."),
    rebuild_index: bool = typer.Option(False, "--rebuild-index", help="Force rebuild journey file index."),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON."),
):
    """
    Run impact analysis for a story.
    
    Default: AI-powered analysis (risk, breaking changes).
    --offline: Static analysis (files touched).
    """
    from agent.core.check.impact import run_impact_analysis, update_story_impact_summary
    
    logger = get_logger(__name__)
    console.print(f"[bold blue]🔍 Running impact analysis for {story_id}...[/bold blue]")

    # 1. Generate Analysis
    if not offline:
        console.print("[dim]🤖 Generating AI impact analysis...[/dim]")
    else:
        console.print("[dim]📊 Running static dependency analysis...[/dim]")

    result = run_impact_analysis(
        story_id=story_id,
        offline=offline,
        base=base,
        update_story=update_story,
        provider=provider,
        rebuild_index=rebuild_index
    )

    if result.get("error") and "Story file not found" in result["error"]:
        console.print(f"[bold red]❌ {result['error']}[/bold red]")
        raise typer.Exit(code=1)

    if not result.get("changed_files"):
        console.print("[yellow]⚠️  No files to analyze. Did you stage your changes?[/yellow]")
        return

    # Handle AI failure and fallback to manual entry
    if result.get("error") and "AI Analysis Failed" in result["error"]:
        console.print(f"[bold red]❌ {result['error']}[/bold red]")
        console.print("[dim]Opening editor for manual analysis entry...[/dim]")
        edited = typer.edit(text=result["impact_summary"])
        if edited:
            result["impact_summary"] = edited
            if update_story:
                result["story_updated"] = update_story_impact_summary(story_id, result["impact_summary"])

    # 2. Output
    if json_output:
        import json as _json
        import time as _time

        report = {
            "story_id": story_id,
            "changed_files": result["changed_files"],
            "affected_journeys": result["affected_journeys"],
            "rebuild_timestamp": _time.time(),
        }
        console.print(_json.dumps(report, indent=2))
        return

    # Static Mode Console Printing Details
    if offline:
        # Display detailed reverse dependencies
        console.print("\n[bold]📊 Dependency Analysis:[/bold]")
        for changed_file, dependents in result.get("reverse_dependencies", {}).items():
            console.print(f"\n📄 [cyan]{changed_file}[/cyan]")
            if dependents:
                console.print(
                    f"  [yellow]→ Impacts {len(dependents)} file(s):[/yellow]"
                )
                # Show first 10 dependents
                for dep in sorted(dependents)[:10]:
                    console.print(f"    • {dep}")
                if len(dependents) > 10:
                    console.print(f"    ... and {len(dependents) - 10} more")
            else:
                console.print("  [green]✓ No direct dependents[/green]")

    # Journey Index Updates Printing
    if rebuild_index or result.get("rebuild_result"):
        idx_result = result.get("rebuild_result", {})
        if idx_result:
            console.print("[dim]📇 Rebuilding journey file index...[/dim]")
            console.print(
                f"[dim]  Indexed {idx_result.get('journey_count', 0)} journeys, "
                f"{idx_result.get('file_glob_count', 0)} patterns "
                f"({idx_result.get('rebuild_duration_ms', 0):.0f}ms)[/dim]"
            )
            for w in idx_result.get("warnings", []):
                console.print(f"  [yellow]⚠️  {w}[/yellow]")

    # Affected Journeys Console Print
    if result.get("affected_journeys"):
        from rich.table import Table as RichTable

        jtable = RichTable(title="Affected Journeys", show_lines=True)
        jtable.add_column("Journey ID", style="cyan")
        jtable.add_column("Title")
        jtable.add_column("Matched Files", style="yellow")
        jtable.add_column("Test File", style="green")

        for j in result["affected_journeys"]:
            tests = j.get("tests", [])
            test_str = "\n".join(tests) if tests else "[red]— none —[/red]"
            jtable.add_row(
                j["id"],
                j["title"],
                "\n".join(j["matched_files"][:5]),
                test_str,
            )

        console.print(jtable)

        if result.get("test_markers"):
            cmd_str = "pytest " + " ".join(result["test_markers"])
            console.print(f"\n[bold]Run affected tests:[/bold]\n  [cyan]{cmd_str}[/cyan]")

        if result.get("ungoverned_files"):
            console.print(
                f"\n[yellow]⚠️  {len(result['ungoverned_files'])} file(s) not mapped to any journey:[/yellow]"
            )
            for uf in result["ungoverned_files"][:5]:
                console.print(f"  [dim]• {uf}[/dim]")
            console.print(
                "[dim]  Tip: Run 'agent journey backfill-tests' to link them.[/dim]"
            )
    else:
        console.print("\n[dim]📋 No journeys affected by changed files.[/dim]")

    console.print("\n[bold]Impact Analysis:[/bold]")
    console.print(result["impact_summary"])

    # 4. Update Story Result Print
    if update_story:
        if result.get("story_updated"):
            console.print(f"[bold green]✅ Updated story file.[/bold green]")
        else:
            console.print(f"[yellow]⚠️ Could not update story file.[/yellow]")
