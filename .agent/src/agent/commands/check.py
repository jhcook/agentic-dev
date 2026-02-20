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
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.core.logger import get_logger

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm # Needed now for UI logic
from rich.panel import Panel
import os

# from agent.core.ai import ai_service # Moved to local import
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.config import config
from agent.core.context import context_loader
from agent.core.governance import convene_council_full, _extract_references, _validate_references
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.fixer import InteractiveFixer


console = Console()


def check_journey_coverage(
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Check journey → test coverage for COMMITTED/ACCEPTED journeys.

    Returns:
        Dict with keys: passed (bool), total, linked, missing, warnings (list[str])
    """
    import yaml  # ADR-025: local import

    root = repo_root or config.repo_root
    journeys_dir = root / ".agent" / "cache" / "journeys"
    result: Dict[str, Any] = {
        "passed": True, "total": 0, "linked": 0, "missing": 0, "warnings": [],
    }

    if not journeys_dir.exists():
        return result

    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            state = (data.get("state") or "DRAFT").upper()
            if state not in ("COMMITTED", "ACCEPTED"):
                continue

            result["total"] += 1
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)

            if not tests:
                result["missing"] += 1
                result["warnings"].append(f"{jid}: No tests linked")
                continue

            all_exist = True
            for t in tests:
                tp = Path(t)
                if tp.is_absolute():
                    result["warnings"].append(f"{jid}: Absolute test path '{t}'")
                    all_exist = False
                    continue
                if not (root / tp).exists():
                    result["warnings"].append(f"{jid}: Test file not found: '{t}'")
                    all_exist = False

            if all_exist:
                result["linked"] += 1
            else:
                result["missing"] += 1

    return result


def validate_linked_journeys(story_id: str) -> dict:
    """
    Validate that a story has real linked journeys (not just placeholder JRN-XXX).

    Returns:
        dict with keys: passed (bool), journey_ids (list[str]), error (str|None)
    """
    result = {"passed": False, "journey_ids": [], "error": None}

    # Find story file
    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break

    if not found_file:
        result["error"] = f"Story file not found for {story_id}"
        return result

    content = found_file.read_text(errors="ignore")

    # Extract ## Linked Journeys section
    import re as _re
    match = _re.search(
        r"## Linked Journeys\s*\n(.*?)(?=\n## |\Z)",
        content,
        _re.DOTALL,
    )

    if not match:
        result["error"] = "Story is missing '## Linked Journeys' section"
        return result

    section_text = match.group(1).strip()
    if not section_text:
        result["error"] = "Story '## Linked Journeys' section is empty"
        return result

    # Extract JRN-NNN IDs (exclude placeholder JRN-XXX)
    journey_ids = _re.findall(r"\bJRN-\d+\b", section_text)

    if not journey_ids:
        result["error"] = (
            "No valid journey IDs found in '## Linked Journeys' — "
            "replace the JRN-XXX placeholder with real journey IDs"
        )
        return result

    result["passed"] = True
    result["journey_ids"] = journey_ids
    return result


def validate_story(
    story_id: str = typer.Argument(..., help="The ID of the story to validate."),
    return_bool: bool = False,
    interactive: bool = False
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
        if interactive:
            console.print(f"[bold yellow]⚠️  Story schema validation failed for {story_id}. Launching Interactive Repair...[/bold yellow]")
            fixer = InteractiveFixer()
            
            # Context for fixer
            context = {
                "story_id": story_id,
                "missing_sections": missing,
                "file_path": str(found_file)
            }
            
            options = fixer.analyze_failure("story_schema", context)
            
            # --- UI LAYER FOR INTERACTIVE FIXER ---
            chosen_opt = None
            if not options:
                console.print("[yellow]No fix options available.[/yellow]")
            else:
                is_voice = os.getenv("AGENT_VOICE_MODE") == "1"
                
                if is_voice:
                    console.print("\nFound the following fix options:")
                    for i, opt in enumerate(options):
                        title = scrub_sensitive_data(opt.get('title', 'Unknown'))
                        desc = scrub_sensitive_data(opt.get('description', ''))
                        console.print(f"Option {i+1}: {title}. {desc}")
                else:
                    console.print("\n[bold cyan]🔧 Fix Options:[/bold cyan]")
                    for i, opt in enumerate(options):
                        title = scrub_sensitive_data(opt.get('title', 'Unknown'))
                        desc = scrub_sensitive_data(opt.get('description', ''))
                        console.print(f"[bold]{i+1}. {title}[/bold]")
                        console.print(f"   {desc}")
                    
                if is_voice:
                    # Flush output buffer with newline so readline() catches it immediately
                    console.print("Select an option (or say quit):")
                    choice = Prompt.ask("", default="1")
                else:
                    choice = Prompt.ask("Select an option (or 'q' to quit)", default="1")
                
                if choice.lower() != 'q':
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(options):
                            chosen_opt = options[idx]
                    except ValueError:
                        pass
            
            if chosen_opt:
                 # Preview diff
                 new_to_write = chosen_opt.get("patched_content", "")
                 safe_preview = scrub_sensitive_data(new_to_write[:500])
                 console.print(Panel(safe_preview + "...", title="Preview (First 500 chars)"))
                 
                 if Confirm.ask("Apply this change?"):
                    if fixer.apply_fix(chosen_opt, found_file):
                        console.print(f"[green]✅ Applied fix to {found_file.name}[/green]")
                        
                        # Verify
                        def check():
                            console.print("[dim]🔄 Verifying fix...[/dim]")
                            # lightweight re-check
                            c = found_file.read_text(errors="ignore")
                            is_valid = all(f"## {s}" in c for s in required_sections)
                            if is_valid:
                                console.print("[bold green]✅ Verification Passed![/bold green]")
                            else:
                                console.print("[bold red]❌ Verification Failed.[/bold red]")
                            return is_valid
                            
                        # Run verify loop (auto-revert on failure logic is in Core)
                        # We just need to report success to caller
                        if fixer.verify_fix(check):
                            return True
                        else:
                             # Core fixer should have auto-reverted if verify failed
                             console.print("[yellow]⏪ Fix was reverted due to verification failure.[/yellow]")
                    else:
                        console.print("[red]❌ Failed to apply fix.[/red]")
                        
            
        if not interactive:
            console.print(f"[bold red]❌ Story schema validation failed for {story_id}[/bold red]")
            console.print(f"Missing sections: {', '.join(missing)}")
            
        if return_bool:
            return False
        raise typer.Exit(code=1)
    else:
        console.print(f"[bold green]✅ Story schema validation passed for {story_id}[/bold green]")
        if return_bool:
            return True



def _print_reference_summary(console: Console, roles_data: list, ref_metrics: dict, finding_validation: dict | None = None) -> None:
    """Print a Governance Validation Summary combining finding validation and reference checks."""
    from rich.table import Table as RefTable

    ref_table = RefTable(title="🔍 Governance Validation Summary", show_lines=True)
    ref_table.add_column("Role", style="cyan")
    # Finding validation columns
    ref_table.add_column("Findings", justify="right", style="bold")
    ref_table.add_column("Validated", justify="right", style="green")
    ref_table.add_column("Filtered", justify="right", style="red")
    # Reference validation columns
    ref_table.add_column("Refs Cited", justify="right", style="dim")
    ref_table.add_column("Refs Valid", justify="right", style="dim green")
    ref_table.add_column("Refs Invalid", justify="right", style="dim red")

    has_data = False
    for role in roles_data:
        fv = role.get("finding_validation", {})
        f_total = fv.get("total", 0)
        f_validated = fv.get("validated", 0)
        f_filtered = fv.get("filtered", 0)

        # Skip roles that had nothing to validate (no AI findings produced)
        if f_total == 0:
            continue

        refs = role.get("references", {})
        if isinstance(refs, dict):
            cited = refs.get("cited", [])
            valid = refs.get("valid", [])
            invalid = refs.get("invalid", [])
        else:
            cited, valid, invalid = [], [], []

        # Style filtered count red if > 0
        filtered_str = f"[bold red]{f_filtered}[/bold red]" if f_filtered > 0 else str(f_filtered)

        ref_table.add_row(
            role.get("name", "Unknown"),
            str(f_total),
            str(f_validated),
            filtered_str,
            str(len(cited)),
            str(len(valid)),
            str(len(invalid)),
        )
        has_data = True

    # Aggregate row
    total_refs = ref_metrics.get("total_refs", 0)
    citation_rate = ref_metrics.get("citation_rate", 0.0)
    hallucination_rate = ref_metrics.get("hallucination_rate", 0.0)

    fv_agg = finding_validation or {}
    agg_total = fv_agg.get("total_ai_findings", 0)
    agg_validated = fv_agg.get("validated", 0)
    agg_filtered = fv_agg.get("filtered_false_positives", 0)
    fp_rate = fv_agg.get("false_positive_rate", 0.0)

    agg_filtered_str = f"[bold red]{agg_filtered}[/bold red]" if agg_filtered > 0 else str(agg_filtered)

    ref_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{agg_total}[/bold]",
        f"[bold]{agg_validated}[/bold]",
        agg_filtered_str,
        f"[bold]{total_refs}[/bold]",
        f"[bold]{len(ref_metrics.get('valid', []))}[/bold]",
        f"[bold]{len(ref_metrics.get('invalid', []))}[/bold]",
    )

    if has_data or total_refs > 0 or agg_total > 0:
        console.print(ref_table)
        summary_parts = []
        if agg_total > 0:
            summary_parts.append(f"False Positive Rate: {fp_rate:.0%}")
        if total_refs > 0:
            summary_parts.append(f"Citation Rate: {citation_rate:.0%}")
            summary_parts.append(f"Hallucination Rate: {hallucination_rate:.0%}")
        if summary_parts:
            console.print(f"[dim]{' | '.join(summary_parts)}[/dim]")
    else:
        console.print("[dim]🔍 No governance findings or references to validate.[/dim]")


def preflight(
    story_id: Optional[str] = typer.Option(None, "--story", help="The story ID to validate against."),
    offline: bool = typer.Option(False, "--offline", help="Disable AI-powered governance review."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)"),
    report_file: Optional[Path] = typer.Option(None, "--report-file", help="Path to save the preflight report as JSON."),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip running tests."),
    ignore_tests: bool = typer.Option(False, "--ignore-tests", help="Run tests but ignore failure (informational only)."),
    interactive: bool = typer.Option(False, "--interactive", help="Enable interactive repair mode."),
    panel_engine: Optional[str] = typer.Option(None, "--panel-engine", help="Override panel engine: 'adk' or 'native'."),
    thorough: bool = typer.Option(False, "--thorough", help="Enable thorough AI review with full-file context and post-processing validation (uses more tokens).")
):
    """
    Run preflight checks (linting, tests, and optional AI governance review).

    Args:
        story_id: The ID of the story to validate.
        offline: Disable AI-powered governance review.
        base: Base branch for comparison (defaults to staged changes).
        provider: Force a specific AI provider (gh, gemini, vertex, openai, anthropic).
        report_file: Path to save the preflight report as JSON.
        skip_tests: Skip running tests.
        ignore_tests: Run tests but ignore failure.
        panel_engine: Override panel engine ('adk' or 'native').
        thorough: Enable thorough AI review with full-file context and post-processing validation.
    """
    # Apply panel engine override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")

    # Check for unstaged changes (Security Maintenance)
    # Check for unstaged changes (Security Maintenance)
    try:
        unstaged_res = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True)
        if unstaged_res.stdout.strip():
            console.print("[yellow]⚠️  Warning: Unstaged changes detected.[/yellow]")
            console.print("[dim]    Note: The AI will only review what is STAGED for commit.[/dim]")
            # We proceed instead of blocking
    except Exception:
        pass

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
        from agent.core.ai import ai_service
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
    if not validate_story(story_id, return_bool=True, interactive=interactive):
        msg = "Story validation failed."
        console.print(f"[bold red]❌ Preflight failed: {msg}[/bold red]")
        if report_file:
             json_report["error"] = msg
             import json
             report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)

    # 1.2 Journey Gate (INFRA-055)
    console.print("\n[bold blue]🗺️  Checking Journey Gate...[/bold blue]")
    journey_gate = validate_linked_journeys(story_id)
    json_report["journey_gate"] = {
        "passed": journey_gate["passed"],
        "journey_ids": journey_gate["journey_ids"],
        "error": journey_gate["error"],
    }
    if not journey_gate["passed"]:
        msg = f"Journey Gate failed: {journey_gate['error']}"
        console.print(f"[bold red]❌ {msg}[/bold red]")
        json_report["overall_verdict"] = "BLOCK"
        if report_file:
            import json
            report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)
    console.print(f"[green]✅ Journey Gate passed — linked: {', '.join(journey_gate['journey_ids'])}[/green]")

    # 1.5 Run Automated Tests
    if skip_tests:
        console.print("[yellow]⏩ Skipping automated tests (--skip-tests passed).[/yellow]")
    else:
        console.print("[bold blue]🧪 Implementing Smart Test Selection...[/bold blue]")
        
        # Identify changed files
        if base:
            cmd = ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
        else:
            cmd = ["git", "diff", "--cached", "--name-only"]
            
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            files = [Path(f) for f in result.stdout.strip().splitlines() if f]
        except Exception as e:
            console.print(f"[bold red]❌ Error finding changed files: {e}[/bold red]")
            files = []

        # Analyze Dependencies
        from agent.core.dependency_analyzer import DependencyAnalyzer
        analyzer = DependencyAnalyzer(Path.cwd())
        
        # Get all files for analysis context
        # Ideally we should list all files, but for now we might rely on dynamic resolution or just simple glob
        # The analzyer helper finds reverse deps requires ALL files to be passed if we want full graph
        # For optimization, we'll try to just identify test files that import changed modules
        # But `find_reverse_dependencies` needs `all_files`.
        
        # Group changes by project
        # Update: Support agent self-development by checking .agent/src paths
        backend_changes = [f for f in files if str(f).startswith("backend/") or str(f).startswith(".agent/src/backend/")]
        mobile_changes = [f for f in files if str(f).startswith("mobile/")]
        web_changes = [f for f in files if str(f).startswith("web/")]
        
        # Root python changes should include .agent python files (excluding tests which are handled differently)
        root_py_changes = []
        for f in files:
            if f.suffix == ".py":
                is_backend = str(f).startswith("backend/") or str(f).startswith(".agent/src/backend/")
                # We want to catch changes in .agent/src/agent (Core) as root python changes that might affect everything
                # check.py previously excluded .agent/, let's allow it but maybe filter distinct subdirs if needed.
                # simpler: just include them.
                if not is_backend:
                    root_py_changes.append(f)
        
        test_commands = []
        
        # --- Python / Backend Strategy ---
        if backend_changes or root_py_changes:
            console.print("[dim]🐍 Analyzing Python dependencies...[/dim]")
            
            # Simple fallback: if backend changed, run pytest backend. 
            # If root changed, run pytest .
            # But let's try strict dependency analysis if possible.
            
            # Find all test files
            all_test_files = list(Path.cwd().rglob("test_*.py")) + list(Path.cwd().rglob("*_test.py"))
            # Filter out non-application test files
            # .agent/ has its own test infra — never run agent tests in preflight
            filtered_tests = []
            for f in all_test_files:
                rel_path = f.relative_to(Path.cwd())
                parts = rel_path.parts
                
                # Exclude node_modules and virtual environments
                if "node_modules" in parts or ".venv" in parts or "venv" in parts:
                    continue
                
                # Exclude agent internal tests — preflight is for application code
                if ".agent" in parts:
                    continue
                    
                filtered_tests.append(rel_path)
            
            all_test_files = filtered_tests
            
            relevant_tests = set()
            
            # Map test files to their imports and check if they import changed files
            # This is "forward" analysis from tests -> code
            changed_set = set(files)
            
            for test_file in all_test_files:
                deps = analyzer.get_file_dependencies(test_file)
                # If test depends on any changed file
                if changed_set.intersection(deps):
                    relevant_tests.add(test_file)
                # OR if the test file itself changed
                if test_file in changed_set:
                    relevant_tests.add(test_file)
            
            # Construct pytest command
            pytest_args = ["-m", "pytest", "-v", "--ignore=.agent"]
            
            if relevant_tests:
                console.print(f"[green]🎯 Found {len(relevant_tests)} relevant test(s).[/green]")
                for rt in relevant_tests:
                    console.print(f"  - {rt}")
                # Pass specific files
                # Note: If list is too long, we might fall back to dirs.
                if len(relevant_tests) < 50:
                    pytest_args.extend([str(t) for t in relevant_tests])
                else:
                    console.print("[yellow]Files list too long, falling back to directory discovery.[/yellow]")
                    if backend_changes: pytest_args.append("backend")
                    if root_py_changes: pytest_args.append(".")
            else:
                # No strictly dependent tests found — trust the analyzer and skip.
                # Running all tests (e.g. `pytest .`) is too broad and pulls in
                # unrelated test suites, causing false failures on PRs.
                console.print("[dim]ℹ️  No test files depend on the changed code — skipping Python tests.[/dim]")
                pytest_args = None

            if pytest_args:
                 # Check for venv
                 # Try root .venv (preferred for isolation)
                 root_venv_python = Path(".venv/bin/python")
                 import sys
                 if root_venv_python.exists():
                      python_exe = str(root_venv_python)
                 else:
                      python_exe = sys.executable
                
                 test_commands.append({
                     "name": "Python Tests",
                     "cmd": [python_exe] + pytest_args,
                     "cwd": Path.cwd()
                 })

        # --- Mobile Strategy (NPM) ---
        if mobile_changes:
            console.print("[dim]📱 Detecting Mobile (React Native) changes...[/dim]")
            mobile_root = Path("mobile")
            pkg_json = mobile_root / "package.json"
            node_modules = mobile_root / "node_modules"
            if pkg_json.exists() and node_modules.exists():
                import json
                scripts = json.loads(pkg_json.read_text()).get("scripts", {})
                
                if "lint" in scripts:
                    test_commands.append({
                        "name": "Mobile Lint",
                        "cmd": ["npm", "run", "lint"],
                        "cwd": mobile_root
                    })
                if "test" in scripts:
                    test_commands.append({
                        "name": "Mobile Tests",
                        "cmd": ["npm", "test"],
                        "cwd": mobile_root
                    })
            elif pkg_json.exists():
                console.print("[dim]  ⏭️  Skipping mobile lint/tests (node_modules not installed — handled by mobile-ci workflow)[/dim]")

        # --- Web Strategy (NPM) ---
        if web_changes:
            console.print("[dim]🌐 Detecting Web (Next.js) changes...[/dim]")
            web_root = Path("web")
            pkg_json = web_root / "package.json"
            node_modules = web_root / "node_modules"
            if pkg_json.exists() and node_modules.exists():
                import json
                scripts = json.loads(pkg_json.read_text()).get("scripts", {})
                
                if "lint" in scripts:
                    test_commands.append({
                        "name": "Web Lint",
                        "cmd": ["npm", "run", "lint"],
                        "cwd": web_root
                    })
                if "test" in scripts:
                    test_commands.append({
                        "name": "Web Tests",
                        "cmd": ["npm", "test"],
                        "cwd": web_root
                    })
            elif pkg_json.exists():
                console.print("[dim]  ⏭️  Skipping web lint/tests (node_modules not installed — handled by web CI workflow)[/dim]")

        # --- EXECUTE CMDS ---
        tests_passed = True
        
        if not test_commands:
             console.print("[green]✅ No relevant tests to run based on changed files.[/green]")
             json_report["overall_verdict"] = "PASS"
        
        for task in test_commands:
            console.print(f"[bold cyan]🏃 Running: {task['name']}[/bold cyan]")
            try:
                # Stream output line by line but capture it for AI analysis
                process = subprocess.Popen(
                    task['cmd'],
                    cwd=task['cwd'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                captured_output = []
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        console.print(line, end="", markup=False)
                        captured_output.append(line)
                        
                # Ensure we get the return code
                rc = process.poll()
                
                # Reconstruct res object for backward compatibility with logic below
                from types import SimpleNamespace
                res = SimpleNamespace(returncode=rc, stdout="".join(captured_output), stderr="")

                
                if res.returncode == 5:
                    # pytest exit code 5 = no tests collected — treat as warning, not failure
                    console.print(f"[yellow]⚠️  {task['name']}: No tests collected (skipped)[/yellow]")
                elif res.returncode != 0:
                    console.print(f"[bold red]❌ {task['name']} FAILED[/bold red]")
                    tests_passed = False
                    
                    if interactive:
                        console.print(f"\n[bold yellow]🔧 Interactive Repair available for {task['name']} failure...[/bold yellow]")
                        
                        # Heuristic: Try to determine the failing file from the command or output
                        # We know 'cmd' often ends with the file path if it was specific
                        target_file = None
                        
                        # 1. Parsing output is most reliable to find specific failure
                        # 1. Parsing output is most reliable to find specific failure
                        if res.stdout:
                             import re
                             # Remove ANSI color codes for cleaner regex
                             ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                             clean_stdout = ansi_escape.sub('', res.stdout)
                             
                             # Match `FAILED tests/core/test_foo.py::test_bar`
                             matches = re.findall(r"FAILED\s+(.+?)::", clean_stdout)
                             # Also match `ERROR collecting tests/core/test_foo.py`
                             matches_collect = re.findall(r"ERROR collecting\s+(.+)", clean_stdout)
                             matches.extend(matches_collect)
                             
                             for m in reversed(matches):
                                 fpath = m.strip().split(" ")[0] # Handle cases where there might be trailing text
                                 possible = task['cwd'] / fpath
                                 if possible.exists():
                                     target_file = possible
                                     break
                                     
                        # 2. Fallback: Check if command explicitly targeted a single file
                        if not target_file:
                             last_arg = task['cmd'][-1]
                             if last_arg.endswith('.py') and (task['cwd'] / last_arg).exists():
                                 target_file = task['cwd'] / last_arg
                        
                        if target_file:
                             console.print(f"[dim]Detected failing test file: {target_file}[/dim]")
                             fixer = InteractiveFixer()
                             
                             fix_context = {
                                 "file_path": str(target_file),
                                 "test_output": (res.stdout or "") + "\n" + (res.stderr or ""),
                                 "content": target_file.read_text(errors="ignore")
                             }
                             
                             options = fixer.analyze_failure("test_failure", fix_context)
                             
                             # --- UI Loop (Duplicated from validate_story, candidate for refactoring to Fixer class UI method) ---
                             while True:
                                 chosen_opt = None
                                 if not options:
                                     console.print("[yellow]No automated fixes available.[/yellow]")
                                     break
                                 else:
                                     console.print("\n[bold cyan]🔧 Test Fix Options:[/bold cyan]")
                                     for i, opt in enumerate(options):
                                         console.print(f"[bold]{i+1}. {opt.get('title')}[/bold]")
                                         console.print(f"   {opt.get('description')}")
                                         
                                     choice = Prompt.ask("Select option (or 'q' to ignore)", default="q")
                                     if choice.lower() == 'q':
                                         break

                                     try:
                                         idx = int(choice) - 1
                                         if 0 <= idx < len(options):
                                             chosen_opt = options[idx]
                                     except Exception:
                                         pass
                                 
                                 if chosen_opt:
                                     if fixer.apply_fix(chosen_opt, target_file):
                                         console.print(f"[green]✅ Applied fix to {target_file.name}[/green]")
                                         # Optional: Re-run verification?
                                         if sorted_cmd := Confirm.ask("Re-run test to verify?", default=True):
                                             # Re-run verify logic using the specific target file for speed
                                             # Fix: Use the same python executable as the task
                                             # task['cmd'][0] is the python executable used for the main test run.
                                             python_exe = task['cmd'][0]
                                             verify_cmd = [python_exe, "-m", "pytest", str(target_file)]
                                             
                                             def verification_callback():
                                                 console.print(f"[dim]Running: {' '.join(verify_cmd)}[/dim]")
                                                 vr = subprocess.run(
                                                     verify_cmd, 
                                                     capture_output=True, 
                                                     text=True
                                                 )
                                                 if vr.returncode != 0:
                                                     console.print(f"[red]❌ Verification Failed:[/red]")
                                                     console.print(vr.stdout + vr.stderr)
                                                     return False
                                                 return True

                                             if fixer.verify_fix(verification_callback):
                                                 console.print(f"[bold green]✅ Test Passed![/bold green]")
                                                 # Fix verified. We should re-run the main task loop to ensure everything is clean,
                                                 # or at least mark this specific test run as passed?
                                                 # Problem: The main `res` object still holds the failure.
                                                 # We need to signal that we recovered.
                                                 
                                                 # Option 1: Retry the *original* command (the full test suite or this specific task)
                                                 console.print("[green]🔄 Re-running full test task to confirm system state...[/green]")
                                                 retry_res = subprocess.run(
                                                    task['cmd'], 
                                                    cwd=task['cwd'], 
                                                    check=False,
                                                    capture_output=True,
                                                    text=True
                                                 )
                                                 if retry_res.returncode == 0:
                                                     tests_passed = True
                                                     console.print(f"[green]✅ {task['name']} PASSED (after fix)[/green]")
                                                     break # Exit the fix loop AND the failure block, proceeding to next task
                                                 else:
                                                     # If it still fails, loop again? Or give up?
                                                     # For now, let's just update `res` and loop again if we wanted to be robust,
                                                     # but to avoid infinite loops, let's just report the new result.
                                                     console.print(f"[red]❌ {task['name']} still failing after fix.[/red]")
                                                     # Update the capture output for the next iteration of analysis?
                                                     # For now, we fall through to failure.
                                                     pass
                                                 
                                                 break # Exit the fix loop
                                             else:
                                                 console.print("[yellow]⚠️ Fix failed verification and was reverted. Please try another option.[/yellow]")
                        else:
                            console.print("[dim]Could not automatically identify a single test file to fix.[/dim]")

                    if not tests_passed and not ignore_tests:
                        break # Stop on first failure if not ignoring
                else:
                    console.print(f"[green]✅ {task['name']} PASSED[/green]")
            except FileNotFoundError:
                 console.print(f"[red]❌ Command not found: {task['cmd'][0]}[/red]")
                 tests_passed = False

        if not tests_passed:
            msg = "Automated tests failed."
            if ignore_tests:
                console.print(f"[yellow]⚠️  {msg} (Ignored by --ignore-tests)[/yellow]")
            else:
                console.print(f"[bold red]❌ {msg} Preflight ABORTED.[/bold red]")
                if report_file:
                    json_report["overall_verdict"] = "BLOCK"
                    json_report["error"] = msg
                    import json
                    report_file.write_text(json.dumps(json_report, indent=2))
                raise typer.Exit(code=1)
        elif test_commands:
            console.print("[bold green]✅ All tests passed.[/bold green]")
            json_report["overall_verdict"] = "PASS"

    # 1.7 ADR Enforcement (Deterministic Gate — INFRA-057)
    console.print("\n[bold blue]📐 Running ADR Enforcement Checks...[/bold blue]")
    from agent.commands.lint import run_adr_enforcement  # ADR-025: local import

    adr_passed = run_adr_enforcement()

    if not adr_passed:
        console.print("[bold red]❌ ADR Enforcement FAILED — violations must be fixed before merge.[/bold red]")
        json_report["adr_enforcement"] = "FAIL"
        if not interactive:
            if report_file:
                json_report["overall_verdict"] = "BLOCK"
                import json
                report_file.write_text(json.dumps(json_report, indent=2))
            raise typer.Exit(code=1)
    else:
        console.print("[green]✅ ADR Enforcement passed.[/green]")
        json_report["adr_enforcement"] = "PASS"

    # 1.8 Journey Coverage Check (Phase 1: Warning — INFRA-058)
    console.print("\n[bold blue]📋 Checking Journey Test Coverage...[/bold blue]")
    coverage_result = check_journey_coverage()
    json_report["journey_coverage"] = coverage_result

    if coverage_result["warnings"]:
        console.print(
            f"[yellow]⚠️  Journey Coverage: {coverage_result['linked']}/{coverage_result['total']}"
            f" COMMITTED journeys linked[/yellow]"
        )
        for w in coverage_result["warnings"][:10]:  # Cap output
            console.print(f"  [yellow]• {w}[/yellow]")
    else:
        console.print("[green]✅ Journey Coverage: All linked.[/green]")

    # 1.9 Journey Impact Mapping (INFRA-059)
    console.print("\n[bold blue]🗺️  Mapping Changed Files → Journeys...[/bold blue]")
    from agent.db.journey_index import (
        get_affected_journeys as _get_affected,
        is_stale as _is_stale,
        rebuild_index as _rebuild_idx,
    )
    from agent.db.init import get_db_path as _get_db_path
    import sqlite3 as _sqlite3

    _db = _sqlite3.connect(_get_db_path())
    _journeys_dir = config.journeys_dir
    _repo_root = config.repo_root

    if _is_stale(_db, _journeys_dir):
        _idx = _rebuild_idx(_db, _journeys_dir, _repo_root)
        console.print(
            f"[dim]  Rebuilt index: {_idx['journey_count']} journeys, "
            f"{_idx['file_glob_count']} patterns[/dim]"
        )

    # Compute changed files early for journey mapping
    _pf_cmd = (
        ["git", "diff", "--name-only", f"origin/{base}...HEAD"]
        if base
        else ["git", "diff", "--cached", "--name-only"]
    )
    _pf_res = subprocess.run(_pf_cmd, capture_output=True, text=True)
    _pf_files = _pf_res.stdout.strip().splitlines()
    _pf_files = [f for f in _pf_files if f]

    if _pf_files:
        _affected = _get_affected(_db, _pf_files, _repo_root)
        if _affected:
            _test_files: list[str] = []
            for _j in _affected:
                _test_files.extend(_j.get("tests", []))
            console.print(
                f"[cyan]  {len(_affected)} journey(s) affected by changed files.[/cyan]"
            )
            if _test_files:
                _cmd_str = "pytest " + " ".join(sorted(set(_test_files)))
                console.print(f"  [bold]Run:[/bold] [cyan]{_cmd_str}[/cyan]")
            json_report["affected_journeys"] = _affected
        else:
            console.print("[dim]  No journeys affected.[/dim]")
    else:
        console.print("[dim]  No changed files for journey mapping.[/dim]")

    _db.close()

    # 2. Get Changed Files (for AI review)
    # Re-run diff cleanly
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
            
            
    # Load full context (rules + instructions + ADRs)
    full_context = context_loader.load_context()
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    adrs_content = full_context.get("adrs", "")
    
    # Cap diff size - if larger than chunk limit, we might need a smart splitter, 
    # but for assimilating roles, we send the same diff to each role agent.
    # We'll stick to a reasonable cap for now to fit in context.
    diff_cmd = cmd = ["git", "diff", "--cached", "-U10", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", "-U10", "."]
    diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
    # Full diff for chunking
    full_diff = diff_res.stdout
    if not full_diff:
        full_diff = ""
        
    # --- SCRUBBING ---
    if not offline:
        console.print("[dim]🔒 Scrubbing sensitive data from diff before AI analysis...[/dim]")
        full_diff = scrub_sensitive_data(full_diff)
        story_content = scrub_sensitive_data(story_content) # Scrub story too just in case
        rules_content = scrub_sensitive_data(rules_content)
        instructions_content = scrub_sensitive_data(instructions_content)
    # -----------------

    if not offline:
        # Validate credentials before AI governance review
        from agent.core.auth.credentials import validate_credentials
        from agent.core.auth.errors import MissingCredentialsError
        try:
            validate_credentials(check_llm=True)
        except MissingCredentialsError as e:
            console.print(f"[yellow]⚠️  AI Governance Review skipped (credentials missing): {e}[/yellow]")
            # If AI is default, we don't hard crash here, just warn and continue offline behavior.
            json_report["overall_verdict"] = "PASS" if tests_passed else "FAIL"
            # Return early if credentials are missing
            if not interactive:
                exit_code = 0 if tests_passed else 1
                raise typer.Exit(code=exit_code)
            return

        # Interactive repair loop — re-run governance after each fix
        MAX_GOVERNANCE_RETRIES = 3
        governance_passed = False
        
        for governance_attempt in range(MAX_GOVERNANCE_RETRIES):
            if governance_attempt > 0:
                console.print(f"\n[bold cyan]🔄 Re-running Governance Council (attempt {governance_attempt + 1}/{MAX_GOVERNANCE_RETRIES})...[/bold cyan]")
                
                # Re-compute diff after fix was applied
                diff_cmd = ["git", "diff", "--cached", "-U10", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", "-U10", "."]
                diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
                full_diff = diff_res.stdout or ""
                
                # Re-scrub sensitive data
                full_diff = scrub_sensitive_data(full_diff)
                
                # Re-load story content (might have been modified by fixer)
                story_content = ""
                for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
                    if file_path.name.startswith(story_id):
                        story_content = file_path.read_text(errors="ignore")
                        break
                story_content = scrub_sensitive_data(story_content)

            with console.status("[bold cyan]🤖 Convening AI Governance Council (Running checks)...[/bold cyan]"):
                result = convene_council_full(
                    story_id=story_id,
                    story_content=story_content,
                    rules_content=rules_content,
                    instructions_content=instructions_content,
                    full_diff=full_diff,
                    report_file=report_file,
                    council_identifier="preflight",
                    adrs_content=adrs_content,
                    thorough=thorough,
                    progress_callback=None # Silence individual role progress to reduce noise
                )

            # Merge AI report details
            if "json_report" in result:
                 json_report.update(result["json_report"])

            if result["verdict"] not in ["BLOCK", "FAIL"]:
                governance_passed = True
                break  # Council passed — exit the retry loop
            
            # --- BLOCKED: Display findings ---
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
                        lines.append(f"SUMMARY:")
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
            fix_applied = False
            if interactive and blocking_findings:
                console.print("\n[bold yellow]🔧 Interactive Repair Available for Blocking Findings...[/bold yellow]")
                
                target_file_path = None
                for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
                    if file_path.name.startswith(story_id):
                        target_file_path = file_path
                        break
                
                if target_file_path:
                    fixer = InteractiveFixer()
                    context = {
                        "story_id": story_id,
                        "findings": blocking_findings,
                        "file_path": str(target_file_path)
                    }
                    
                    try:
                        options = fixer.analyze_failure("governance_rejection", context)
                    except Exception as e:
                        console.print(f"[yellow]⚠️  Automated fix generation failed: {e}[/yellow]")
                        options = []
                    
                    chosen_opt = None
                    if not options:
                       console.print("[yellow]No automated fix options generated.[/yellow]")
                    else:
                       is_voice = os.getenv("AGENT_VOICE_MODE") == "1"
                       if is_voice:
                            console.print("\nFound the following fix options:")
                            for i, opt in enumerate(options):
                                console.print(f"Option {i+1}: {opt.get('title', 'Option')}. {opt.get('description', '')}")
                       else:
                           console.print("\n[bold cyan]Choose a fix option to apply:[/bold cyan]")
                           for i, opt in enumerate(options):
                               console.print(f"[bold]{i+1}. {opt.get('title', 'Option')}[/bold]")
                               console.print(f"   {opt.get('description', '')}")
                       
                       if is_voice:
                           console.print("Select option (or say quit):")
                           choice = Prompt.ask("", default="q")
                       else:
                           choice = Prompt.ask("Select option (or 'q' to ignore)", default="q")
                       if choice.lower() != 'q':
                           try:
                               idx = int(choice) - 1
                               if 0 <= idx < len(options):
                                   chosen_opt = options[idx]
                           except Exception:
                               pass
                               
                    if chosen_opt:
                        if fixer.apply_fix(chosen_opt, target_file_path):
                            console.print("[bold green]✅ Fix applied successfully.[/bold green]")
                            # Re-stage the modified file so the next diff picks it up
                            subprocess.run(["git", "add", str(target_file_path)], capture_output=True, text=True)
                            fix_applied = True
                            console.print("[bold cyan]🔄 Re-running governance checks to verify fix...[/bold cyan]")
                            continue  # Loop back to re-run governance council
                        else:
                            console.print("[red]❌ Failed to apply fix.[/red]")

            # If we reach here without a fix applied, break out — no point retrying
            break
        
        # After the loop: check outcome

        # Display Reference Summary Table (INFRA-060 AC-9)
        _ref_metrics = result.get("json_report", {}).get("reference_metrics", {})
        _roles_data = result.get("json_report", {}).get("roles", [])
        _fv_metrics = result.get("json_report", {}).get("finding_validation", {})
        if _ref_metrics.get("total_refs", 0) > 0 or _roles_data:
            _print_reference_summary(console, _roles_data, _ref_metrics, _fv_metrics)

        if not governance_passed:
            if report_file:
                json_report["overall_verdict"] = "BLOCK"
                json_report["error"] = "Preflight blocked by governance checks."
                import json
                report_file.write_text(json.dumps(json_report, indent=2))

            raise typer.Exit(code=1)
    
    console.print("[bold green]✅ Preflight checks passed![/bold green]")

    if report_file:
         import json
         # Ensure we have a verdict if we skipped AI or it passed
         if json_report["overall_verdict"] == "UNKNOWN":
             json_report["overall_verdict"] = "PASS"
             
         report_file.write_text(json.dumps(json_report, indent=2))


def impact(
    story_id: str = typer.Argument(..., help="The ID of the story."),
    offline: bool = typer.Option(False, "--offline", help="Disable AI-powered impact analysis."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    update_story: bool = typer.Option(False, "--update-story", help="Update the story file with the impact analysis."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)."),
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


def panel(
    input_arg: Optional[str] = typer.Argument(None, help="Story ID OR a question/instruction for the panel."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison (e.g. main)."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)."),
    apply: bool = typer.Option(False, "--apply", help="Automatically apply the panel's advice to the Story/Runbook."),
    panel_engine: Optional[str] = typer.Option(None, "--panel-engine", help="Override panel engine: 'adk' or 'native'.")
):
    """
    Convening the Governance Panel to review changes or discuss design.
    """
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

    full_context = context_loader.load_context()
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    adrs_content = full_context.get("adrs", "")
    
    # 4. Scrum & Run
    full_diff = scrub_sensitive_data(full_diff)
    scrubbed_content = scrub_sensitive_data(story_content)
    rules_content = scrub_sensitive_data(rules_content)
    instructions_content = scrub_sensitive_data(instructions_content)


    with console.status("[bold cyan]🤖 Convening AI Governance Panel (Consultation)...[/bold cyan]"):
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
            target_file.write_text(updated_content)
            console.print(f"[bold green]✅ Applied advice to {target_file.name}[/bold green]")
        else:
             console.print("[bold red]❌ Failed to generate valid update (Content empty or too short).[/bold red]")

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
