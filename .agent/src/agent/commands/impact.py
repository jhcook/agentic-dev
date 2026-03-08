# Copyright 2026 Justin Cook
import re
import subprocess
import time
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from agent.core.logger import get_logger
from agent.core.config import config
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.ai.prompts import generate_impact_prompt

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
    logger = get_logger(__name__)
    console.print(f"[bold blue]🔍 Running impact analysis for {story_id}...[/bold blue]")

    # 1. Find the story file
    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break
            
    if not found_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         raise typer.Exit(code=1)

    story_content = found_file.read_text(errors="ignore")

    # 2. Get Diff
    if base:
        # Use simple revision range without forcing origin/
        # This allows HEAD~, local branches, or tags
        cmd = ["git", "diff", "--name-only", f"{base}...HEAD"]
        diff_cmd = ["git", "diff", f"{base}...HEAD", "."]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        diff_cmd = ["git", "diff", "--cached", "."]
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().splitlines()
    
    if not files or files == ['']:
        console.print("[yellow]⚠️  No files to analyze. Did you stage your changes?[/yellow]")
        return

    # 3. Generate Analysis
    analysis = "Static Impact Analysis:\n" + "\n".join(f"- {f}" for f in files)
    
    if not offline:
        # AI Mode
        # Credentials validated by @with_creds decorator in main.py
        console.print("[dim]🤖 Generating AI impact analysis...[/dim]")
        from agent.core.ai import ai_service  # ADR-025: lazy init
        if provider:
            ai_service.set_provider(provider)
            
        diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
        full_diff = diff_res.stdout
        
        # Scrubbing
        full_diff = scrub_sensitive_data(full_diff)
        story_content = scrub_sensitive_data(story_content)
        
        prompt = generate_impact_prompt(diff=full_diff, story=story_content)
        logger.debug(
            "AI impact prompt: %d chars, diff: %d chars",
            len(prompt),
            len(full_diff),
        )
        
        try:
            analysis = ai_service.get_completion(prompt)
        except Exception as e:
            console.print(f"[bold red]❌ AI Analysis Failed: {e}[/bold red]")
            console.print("[dim]Opening editor for manual analysis entry...[/dim]")
            edited = typer.edit(text=analysis)
            if edited:
                analysis = edited
            
    else:
        # Static Mode - Use Dependency Analyzer
        console.print("[dim]📊 Running static dependency analysis...[/dim]")
        
        from agent.core.dependency_analyzer import DependencyAnalyzer
        
        repo_root = Path.cwd()
        analyzer = DependencyAnalyzer(repo_root)
        
        # Convert file strings to Path objects
        changed_files = [Path(f) for f in files]
        
        # Get all Python and JS files in repo
        all_files = []
        for pattern in ['**/*.py', '**/*.js', '**/*.ts', '**/*.tsx']:
            all_files.extend(repo_root.glob(pattern))
        all_files = [f.relative_to(repo_root) for f in all_files]
        
        # Find reverse dependencies
        reverse_deps = analyzer.find_reverse_dependencies(changed_files, all_files)
        
        total_impacted = sum(len(deps) for deps in reverse_deps.values())
        logger.debug(
            "Dependency graph: %d changed files, %d all files, %d reverse deps",
            len(changed_files),
            len(all_files),
            total_impacted,
        )
        
        # Build analysis summary
        components = set()
        for f in files:
            parts = Path(f).parts
            if len(parts) > 1:
                components.add(parts[0])
            else:
                components.add("root")
        
        analysis = f"""## Impact Analysis Summary

**Components**: {', '.join(sorted(components))}
**Files Changed**: {len(files)}
**Reverse Dependencies**: {total_impacted} file(s) impacted

### Changed Files
{chr(10).join('- ' + f for f in files)}

### Risk Summary
- Blast radius: {'🔴 High' if total_impacted > 20 else '🟡 Medium' if total_impacted > 5 else '🟢 Low'} ({total_impacted} dependent files)
- Components affected: {len(components)}
"""
        
        # Display detailed reverse dependencies
        console.print("\n[bold]📊 Dependency Analysis:[/bold]")
        for changed_file, dependents in reverse_deps.items():
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

    # 3b. Journey Impact Mapping (INFRA-059)
    from agent.db.journey_index import (
        get_affected_journeys,
        is_stale,
        rebuild_index as rebuild_journey_index,
    )
    from agent.db.init import get_db_path
    import sqlite3 as _sqlite3

    db_path = get_db_path()
    jconn = _sqlite3.connect(db_path)
    repo_root_path = config.repo_root
    journeys_dir = config.journeys_dir

    if rebuild_index or is_stale(jconn, journeys_dir):
        console.print("[dim]📇 Rebuilding journey file index...[/dim]")
        idx_result = rebuild_journey_index(jconn, journeys_dir, repo_root_path)
        console.print(
            f"[dim]  Indexed {idx_result['journey_count']} journeys, "
            f"{idx_result['file_glob_count']} patterns "
            f"({idx_result['rebuild_duration_ms']:.0f}ms)[/dim]"
        )
        for w in idx_result.get("warnings", []):
            console.print(f"  [yellow]⚠️  {w}[/yellow]")

    affected = get_affected_journeys(jconn, files, repo_root_path)
    jconn.close()

    if affected:
        from rich.table import Table as RichTable

        jtable = RichTable(title="Affected Journeys", show_lines=True)
        jtable.add_column("Journey ID", style="cyan")
        jtable.add_column("Title")
        jtable.add_column("Matched Files", style="yellow")
        jtable.add_column("Test File", style="green")

        test_markers: list[str] = []
        for j in affected:
            tests = j.get("tests", [])
            test_str = "\n".join(tests) if tests else "[red]— none —[/red]"
            jtable.add_row(
                j["id"],
                j["title"],
                "\n".join(j["matched_files"][:5]),
                test_str,
            )
            for t in tests:
                test_markers.append(t)

        console.print(jtable)

        if test_markers:
            cmd_str = "pytest " + " ".join(sorted(set(test_markers)))
            console.print(f"\n[bold]Run affected tests:[/bold]\n  [cyan]{cmd_str}[/cyan]")

        # Warn about ungoverned files
        governed_files = set()
        for j in affected:
            governed_files.update(j["matched_files"])
        ungoverned = [f for f in files if f not in governed_files]
        if ungoverned:
            console.print(
                f"\n[yellow]⚠️  {len(ungoverned)} file(s) not mapped to any journey:[/yellow]"
            )
            for uf in ungoverned[:5]:
                console.print(f"  [dim]• {uf}[/dim]")
            console.print(
                "[dim]  Tip: Run 'agent journey backfill-tests' to link them.[/dim]"
            )
    else:
        console.print("\n[dim]📋 No journeys affected by changed files.[/dim]")

    # JSON output mode (INFRA-059 AC-5)
    if json_output:
        import json as _json
        import time as _time

        report = {
            "story_id": story_id,
            "changed_files": files,
            "affected_journeys": affected,
            "rebuild_timestamp": _time.time(),
        }
        console.print(_json.dumps(report, indent=2))
        return

    console.print("\n[bold]Impact Analysis:[/bold]")
    console.print(analysis)

    # 4. Update Story
    if update_story:
        console.print(f"[dim]✏️ Updating story file: {found_file.name}...[/dim]")
        # We need to replace the content under "## Impact Analysis Summary"
        # Simple regex replacement or just finding the header
        import re
        
        # Normalize the analysis to ensure it has the header if missing from AI (it shouldn't be based on prompt)
        if "## Impact Analysis Summary" not in analysis:
            analysis = "## Impact Analysis Summary\n" + analysis
            
        # Regex to match ## Impact Analysis Summary until the next ## Header or End of String
        pattern = r"(## Impact Analysis Summary)([\s\S]*?)(?=\n## |$)"
        
        if re.search(pattern, story_content):
            new_content = re.sub(pattern, analysis.strip(), story_content)
            found_file.write_text(new_content)
            console.print(f"[bold green]✅ Updated {found_file.name}[/bold green]")
        else:
            console.print(f"[yellow]⚠️  Could not find '## Impact Analysis Summary' section in {found_file.name}. Appending...[/yellow]")
            found_file.write_text(story_content + "\n\n" + analysis)
            console.print(f"[bold green]✅ Appended to {found_file.name}[/bold green]")
