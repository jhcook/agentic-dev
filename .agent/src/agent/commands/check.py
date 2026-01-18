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
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from agent.core.ai import ai_service
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.config import config
from agent.core.context import context_loader
from agent.core.governance import convene_council_full
from agent.core.utils import infer_story_id, scrub_sensitive_data

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

    # 1.5 Run Automated Tests
    console.print("[bold blue]🧪 Running Automated Tests...[/bold blue]")
    try:
        # Determine test command
        # 1. Try root .venv (preferred for isolation)
        root_venv_python = Path(".venv/bin/python")
        if root_venv_python.exists():
             test_cmd = [str(root_venv_python), "-m", "pytest", ".agent/tests"]
        else:
             # 2. Fallback to system executor (sys.executable)
             # This handles cases where we are running inside the venv
             import sys
             test_cmd = [sys.executable, "-m", "pytest", ".agent/tests"]
        
        # Check if we are in the root or need to adjust path? 
        # Assuming run from repo root as per standard
        
        result = subprocess.run(test_cmd, capture_output=False, check=False)
        
        if result.returncode != 0:
            msg = "Automated tests failed. Preflight ABORTED."
            console.print(f"[bold red]❌ {msg}[/bold red]")
            if report_file:
                json_report["overall_verdict"] = "BLOCK"
                json_report["error"] = "Automated tests failed"
                import json
                report_file.write_text(json.dumps(json_report, indent=2))
            raise typer.Exit(code=1)
        else:
            console.print("[bold green]✅ Automated tests passed.[/bold green]")

    except FileNotFoundError:
        console.print("[yellow]⚠️  Could not find test runner (pytest). Skipping tests but warning...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error running tests: {e}[/bold red]")
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

    if ai:
        verdict = convene_council_full(
            console=console,
            story_id=story_id,
            story_content=story_content,
            rules_content=rules_content,
            instructions_content=instructions_content,
            full_diff=full_diff,
            report_file=report_file,
            mode="gatekeeper"
        )
        if verdict in ["BLOCK", "FAIL"]:
             # convene_council_full handles printing the error/report location
             raise typer.Exit(code=1)
    
    console.print("[bold green]✅ Preflight checks passed![/bold green]")


def impact(
    story_id: str = typer.Argument(..., help="The ID of the story."),
    ai: bool = typer.Option(False, "--ai", help="Enable AI-powered impact analysis."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    update_story: bool = typer.Option(False, "--update-story", help="Update the story file with the impact analysis."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, openai).")
):
    """
    Run impact analysis for a story.
    
    Default: Static analysis (files touched).
    --ai: AI-powered analysis (risk, breaking changes).
    """
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
    analysis = ""
    
    if ai:
        # AI Mode
        console.print("[dim]🤖 Generating AI impact analysis...[/dim]")
        if provider:
            ai_service.set_provider(provider)
            
        diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
        full_diff = diff_res.stdout
        
        # Scrubbing
        full_diff = scrub_sensitive_data(full_diff)
        story_content = scrub_sensitive_data(story_content)
        
        prompt = generate_impact_prompt(diff=full_diff, story=story_content)
        
        try:
            analysis = ai_service.get_completion(prompt)
        except Exception as e:
            console.print(f"[bold red]❌ AI Analysis Failed: {e}[/bold red]")
            raise typer.Exit(code=1)
            
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
        
        # Build analysis summary
        components = set()
        for f in files:
            parts = Path(f).parts
            if len(parts) > 1:
                components.add(parts[0])
            else:
                components.add("root")
        
        analysis = f"""## Impact Analysis Summary
Components touched: {', '.join(files)}
Reverse dependencies: {total_impacted} file(s) impacted
Workflows affected: {', '.join(components)}
Risks identified: {total_impacted} files depend on changed code
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


def panel(
    story_id: Optional[str] = typer.Argument(None, help="The ID of the story. If excluded, infers from content."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, openai).")
):
    """
    Convening the Governance Panel to review changes.
    """
    # 0. Configure Provider Override if set
    if provider:
        ai_service.set_provider(provider)
        
    if not story_id:
        story_id = infer_story_id()
        if not story_id:
             console.print("[bold red]❌ Story ID is required (and could not be inferred).[/bold red]")
             raise typer.Exit(code=1)

    console.print(f"[bold cyan]🤖 Convening the Governance Panel for {story_id}...[/bold cyan]")

    # 1. Get Changed Files
    if base:
        cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().splitlines()
    
    if not files or files == ['']:
        console.print("[yellow]⚠️  No files to review. Did you stage your changes?[/yellow]")
        return

    # 2. Get Full Diff
    diff_cmd = ["git", "diff", "--cached", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", "."]
    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
    full_diff = diff_res.stdout
    if not full_diff:
        full_diff = ""

    # 3. Load Context
    story_content = ""
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            story_content = file_path.read_text(errors="ignore")
            break
    
    if not story_content:
         console.print(f"[yellow]⚠️  Story {story_id} file not found. Reviewing without specific story context.[/yellow]")

    full_context = context_loader.load_context()
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    
    # 4. Scrum & Run
    full_diff = scrub_sensitive_data(full_diff)
    story_content = scrub_sensitive_data(story_content)
    rules_content = scrub_sensitive_data(rules_content)
    instructions_content = scrub_sensitive_data(instructions_content)

    convene_council_full(
        console=console,
        story_id=story_id,
        story_content=story_content,
        rules_content=rules_content,
        instructions_content=instructions_content,
        full_diff=full_diff,
        mode="consultative"
    )

def run_ui_tests(
    story_id: Optional[str] = typer.Argument(None, help="The ID of the story (for context/logging)."),
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter test flows by keyword.")
):
    """
    Run UI journey tests using Maestro.
    """
    import shutil
    import subprocess
    import time
    from pathlib import Path
    
    # 1. Setup Logging
    log_file = Path(".agent/logs/agent_run_ui_tests.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(msg: str, console_msg: Optional[str] = None):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {msg}\n"
        with open(log_file, "a") as f:
            f.write(entry)
        if console_msg:
            console.print(console_msg)
        elif console_msg is not False: # Pass False to suppress console
            pass

    console.print("[bold blue]📱 Initiating UI Test Run (Maestro)[/bold blue]")
    log(f"Starting run_ui_tests. Story: {story_id}, Filter: {filter}")

    # 2. Check Prerequisites
    maestro_path = shutil.which("maestro")
    if not maestro_path:
        msg = "Maestro CLI is not installed or not in PATH."
        log(f"Error: {msg}", console_msg=f"[bold red]❌ {msg}[/bold red]")
        console.print("Please install Maestro: https://maestro.mobile.dev/")
        raise typer.Exit(code=1)

    # 3. Find Test Flows
    search_paths = [Path("tests/ui"), Path(".maestro")]
    test_flows = []
    
    for path in search_paths:
        if path.exists() and path.is_dir():
            found = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
            test_flows.extend(found)
            
    if not test_flows:
        msg = f"No .yaml/.yml test flows found in {', '.join([str(p) for p in search_paths])}."
        log(f"Info: {msg}", console_msg=f"[yellow]⚠️  {msg}[/yellow]")
        raise typer.Exit(code=0)

    # 4. Filter Flows
    if filter:
        test_flows = [f for f in test_flows if filter in f.name]
        if not test_flows:
            msg = f"No test flows match filter '{filter}'."
            log(f"Info: {msg}", console_msg=f"[yellow]⚠️  {msg}[/yellow]")
            raise typer.Exit(code=0)

    log(f"Found {len(test_flows)} flows: {[f.name for f in test_flows]}")
    console.print(f"Found {len(test_flows)} test flows.")

    # 5. Execute Flows
    failed_flows = []
    passed_flows = []

    for flow in test_flows:
        console.print(f"\n[bold cyan]🏃 Running: {flow.name}[/bold cyan]")
        log(f"Running flow: {flow}")
        
        start_time = time.time()
        try:
            # We stream output to console and also capture it? 
            # Maestro output is pretty rich, let's let it stream to stdout 
            # but assume failure if return code != 0
            
            # Using subprocess.run to allow streaming if we didn't capture_output, 
            # but for log capture we might need to capture.
            # Let's verify compatibility. Simple run:
            
            result = subprocess.run(
                [maestro_path, "test", str(flow)],
                check=False  # We handle code manually
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                console.print(f"[green]✅ PASSED ({duration:.2f}s)[/green]")
                log(f"Flow {flow.name} PASSED. Duration: {duration:.2f}s")
                passed_flows.append(flow.name)
            else:
                console.print(f"[red]❌ FAILED ({duration:.2f}s)[/red]")
                log(f"Flow {flow.name} FAILED. Duration: {duration:.2f}s. Exit code: {result.returncode}")
                failed_flows.append(flow.name)
                
        except Exception as e:
            console.print(f"[red]❌ Error executing flow {flow.name}: {e}[/red]")
            log(f"Exception executing {flow.name}: {e}")
            failed_flows.append(flow.name)

    # 6. Summary
    console.print("\n[bold]Test Summary[/bold]")
    console.print(f"Total: {len(test_flows)}")
    console.print(f"[green]Passed: {len(passed_flows)}[/green]")
    
    if failed_flows:
        console.print(f"[red]Failed: {len(failed_flows)}[/red]")
        for f in failed_flows:
             console.print(f" - {f}")
        
        log(f"Run FAILED. Failed flows: {failed_flows}")
        raise typer.Exit(code=1)
    else:
        log("Run PASSED.")
        raise typer.Exit(code=0)
