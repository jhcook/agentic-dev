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
from typing import Any, Dict, Optional

from agent.core.logger import get_logger

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm  # Needed now for UI logic
from rich.panel import Panel
import os

# from agent.core.ai import ai_service # Moved to local import
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.config import config
from agent.core.context import context_loader
from agent.core.governance import convene_council_full
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.fixer import InteractiveFixer

# ── INFRA-103: Re-export extracted helpers so existing mock-patch paths remain valid ──
from agent.core.check.quality import check_journey_coverage, check_code_quality  # noqa: F401
from agent.core.check.system import validate_linked_journeys  # noqa: F401


console = Console()

logger = get_logger(__name__)

from agent.core.check.reporting import print_reference_summary as _print_reference_summary


def _write_preflight_cache(story_id: str, verdict: str) -> None:
    """Write preflight result to cache for `agent pr` to detect (INFRA-138).

    Uses the same schema that ``workflow.py`` reads: ``verdict``, ``story_id``,
    ``commit``, and ``timestamp``.
    """
    try:
        import json as _json
        import time as _time
        _marker_path = config.cache_dir / ".preflight_result"
        _head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        _marker_path.write_text(_json.dumps({
            "story_id": story_id,
            "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
            "commit": _head_sha,
            "verdict": verdict,
        }, indent=2))
    except Exception:
        pass  # Best-effort, non-critical



def validate_story(
    story_id: str = typer.Argument(..., help="Story ID to validate, e.g. INFRA-103"),
) -> None:
    """Validate that a story file has all required sections."""
    from agent.core.check.system import validate_story as _validate_story
    from rich.console import Console
    _console = Console()
    result = _validate_story(story_id)
    if result["passed"]:
        _console.print(f"[bold green]✅ Story schema validation passed for {story_id}[/bold green]")
    else:
        _console.print(f"[bold red]❌ Story schema validation failed for {story_id}[/bold red]")
        if result["error"]:
            _console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)


def preflight(
    story_id: Optional[str] = typer.Option(None, "--story", help="The story ID to validate against."),
    offline: bool = typer.Option(False, "--offline", help="Disable AI-powered governance review."),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch for comparison."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)"),
    report_file: Optional[Path] = typer.Option(None, "--report-file", help="Path to save the preflight report as JSON."),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip running tests."),
    ignore_tests: bool = typer.Option(False, "--ignore-tests", help="Run tests but ignore failure (informational only)."),
    interactive: bool = typer.Option(False, "--interactive", help="Enable interactive repair mode."),
    autoheal: bool = typer.Option(False, "--autoheal", help="Autonomously fix BLOCK verdicts: extract REQUIRED_CHANGES, apply AI edits, re-run per role."),
    budget: int = typer.Option(3, "--budget", help="Max autoheal attempts per blocked role (default: 3)."),
    panel_engine: Optional[str] = typer.Option(None, "--panel-engine", help="Override panel engine: 'adk' or 'native'."),
    thorough: bool = typer.Option(True, "--thorough", help="Enable thorough AI review with full-file context (Default: True)."),
    quick: bool = typer.Option(False, "--quick", help="Opt out of thorough mode for fast/cheap runs."),
    legacy_context: bool = typer.Option(False, "--legacy-context", help="Use full legacy context instead of Oracle Pattern."),
    gate: Optional[str] = typer.Option(None, "--gate", help="Run a specific gate isolated.")
):
    """
    Run preflight checks (linting, tests, and optional AI governance review).

    Args:
        story_id: The ID of the story to validate.
        offline: Disable AI-powered governance review.
        base: Base branch for comparison (defaults to staged changes).
        provider: Force a specific AI provider (gh, gemini, vertex, openai, anthropic, ollama).
        report_file: Path to save the preflight report as JSON.
        skip_tests: Skip running tests.
        ignore_tests: Run tests but ignore failure.
        panel_engine: Override panel engine ('adk' or 'native').
        thorough: Enable thorough AI review with full-file context and post-processing validation.
        legacy_context: Use full legacy context instead of Oracle Pattern.
    """
    import time as _pf_time
    _preflight_start = _pf_time.time()

    # Apply panel engine override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")

    if gate == "quality":
        console.print("[bold blue]🧹 Checking Code Quality (LOC & Imports)...[/bold blue]")
        quality_result = check_code_quality()
        if not quality_result.passed:
            console.print(f"[bold red]❌ {quality_result.name} FAILED[/bold red]")
            console.print(f"[red]{quality_result.details}[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]✅ {quality_result.name} passed.[/green]")
        console.print(f"[dim]{quality_result.details}[/dim]")
        raise typer.Exit(code=0)


    if not offline and not legacy_context:
        try:
            from agent.sync.notion import NotionSync
            sync = NotionSync()
            sync.ensure_synchronized()
        except typer.Exit:
            raise
        except Exception as e:
            logger.debug(f"Could not verify Notion sync state: {e}")
            console.print("[yellow]⚠️  Could not verify Notion sync state. Ensure 'agent sync init' was run.[/yellow]")
            
        try:
            import asyncio
            from agent.sync.notebooklm import ensure_notebooklm_sync
            from rich.status import Status
            console.print("[dim]Synchronizing NotebookLM Context...[/dim]")
            with Status("Synchronizing NotebookLM Context...", console=console) as _sync_status:
                def _update_notebooklm_status_2(msg: str):
                    _sync_status.update(f"Synchronizing NotebookLM Context... [dim]{msg}[/dim]")
                    # For non-interactive/piped environments (like agent console)
                    if not console.is_terminal:
                        console.print(f"  [dim]• {msg}[/dim]")
                asyncio.run(ensure_notebooklm_sync(progress_callback=_update_notebooklm_status_2))
        except Exception as e:
            logger.debug(f"Could not sync with NotebookLM: {e}")
            console.print(f"[yellow]⚠️  NotebookLM sync degraded: {e}[/yellow]")

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
    from agent.core.check.system import validate_story as _validate_story_core
    _story_result = _validate_story_core(story_id)
    if not _story_result["passed"]:
        if _story_result["story_file"] is None:
            msg = f"Story file not found for {story_id}"
            console.print(f"[bold red]❌ Story schema validation failed for {story_id}[/bold red]")
            if report_file:
                 json_report["error"] = msg
                 import json
                 report_file.write_text(json.dumps(json_report, indent=2))
            raise typer.Exit(code=1)
        else:
            msg = _story_result["error"] or "Story validation failed."
            console.print(f"[bold red]❌ Story schema validation failed for {story_id}[/bold red]")
            if interactive:
                from agent.core.fixer import InteractiveFixer
                import rich.prompt
                from pathlib import Path
                
                fixer = InteractiveFixer()
                story_file_path = Path(_story_result["story_file"])
                
                context = {
                    "story_id": story_id,
                    "missing_sections": [msg],
                    "file_path": str(story_file_path)
                }
                options = fixer.analyze_failure("story_schema", context)
                
                if options:
                    if os.getenv("AGENT_VOICE_MODE"):
                        console.print("\n[bold]Found the following fix options:[/bold]")
                        for i, opt in enumerate(options):
                            desc = opt.get('description', '')
                            # For voice mode, we print the option on a single line
                            console.print(f"Option {i + 1}: {opt['title']}. {desc}")
                        
                        selection = rich.prompt.Prompt.ask("\nSelect an option (or say quit)")
                        if selection.lower() in ("q", "quit", "exit"):
                            raise typer.Exit(code=1)
                    else:
                        console.print("\n[bold yellow]🔧 Fix Options:[/bold yellow]")
                        for i, opt in enumerate(options):
                            if opt.get("action") == "open_editor":
                                console.print(f"  [bold]{i + 1}.[/bold] {opt['title']} - {opt['description']}")
                            else:
                                console.print(f"  [bold]{i + 1}.[/bold] {opt['title']}\n     [dim]{opt['description']}[/dim]")
                        
                        selection = rich.prompt.Prompt.ask("\nSelect an option (or 'q' to quit)", default="1")
                        if selection.lower() == 'q':
                            raise typer.Exit(code=1)
                            
                    try:
                        idx = int(selection) - 1
                        if 0 <= idx < len(options):
                            selected_opt = options[idx]
                            
                            if selected_opt.get("action") == "open_editor":
                                fixer.apply_fix(selected_opt, story_file_path)
                            else:
                                console.print("\n[cyan]Applying fix...[/cyan]")
                                if fixer.apply_fix(selected_opt, story_file_path):
                                    console.print(f"[green]✅ Applied fix: {selected_opt['title']}[/green]")
                                else:
                                    console.print("[red]❌ Failed to apply fix[/red]")
                                    raise typer.Exit(code=1)
                            
                            def verify_story_callback():
                                res = _validate_story_core(story_id)
                                return res["passed"]
                            
                            if fixer.verify_fix(verify_story_callback):
                                console.print("[green]✅ Verification Passed[/green]")
                            else:
                                console.print("[red]❌ Verification Failed even after fix.[/red]")
                                raise typer.Exit(code=1)
                        else:
                            console.print("[red]Invalid selection.[/red]")
                            raise typer.Exit(code=1)
                    except ValueError:
                        console.print("[red]Invalid selection input.[/red]")
                        raise typer.Exit(code=1)
                else:
                    console.print("[red]No fix options generated.[/red]")
                    raise typer.Exit(code=1)
            else:
                if report_file:
                     json_report["error"] = msg
                     import json
                     report_file.write_text(json.dumps(json_report, indent=2))
                raise typer.Exit(code=1)

    console.print(f"[bold green]✅ Story schema validation passed for {story_id}[/bold green]")

    # 1.1 Notion Sync Awareness (Oracle Pattern)
    if not legacy_context:
        from agent.core.check.syncing import sync_oracle_pattern
        sync_result = sync_oracle_pattern()
        if sync_result.get("warnings"):
            for w in sync_result["warnings"]:
                console.print(f"[yellow]  ⚠️  {w}[/yellow]")

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
    from agent.core.check.testing import run_smart_test_selection
    import subprocess
    
    test_result = run_smart_test_selection(base, skip_tests, interactive, ignore_tests)
    tests_ok = True
    
    if test_result.get("skipped"):
        console.print("\n[dim]Skipping tests...[/dim]")
    elif test_result.get("error"):
        console.print(f"\n[bold red]❌ Test Selection Failed: {test_result['error']}[/bold red]")
        tests_ok = False
    elif test_result.get("test_commands"):
        console.print("\n[bold blue]🧪 Running Automated Tests...[/bold blue]")
        _test_healer = None
        if autoheal:
            from agent.core.preflight.test_healer import TestHealer
            _test_healer = TestHealer(budget=budget)

        for cmd_info in test_result["test_commands"]:
            cmd_name = cmd_info.get("name", "Tests")
            cmd = cmd_info.get("cmd", [])
            cwd = cmd_info.get("cwd")

            console.print(f"  [bold]Run ({cmd_name}):[/bold] [cyan]{' '.join(str(c) for c in cmd)}[/cyan]")

            try:
                # Stream output live so the terminal doesn't appear frozen.
                # Propagate AGENT_SKIP_KEYRING so pytest subprocess never triggers
                # macOS keychain dialogs (which would block unattended CI runs).
                _test_env = {**os.environ, "AGENT_SKIP_KEYRING": "1"}
                res = subprocess.run(cmd, cwd=cwd, env=_test_env)
                if res.returncode != 0:
                    console.print(f"  [bold red]❌ {cmd_name} failed.[/bold red]")
                    if _test_healer:
                        # Re-run with capture to collect the traceback for healing.
                        cap = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=_test_env)
                        traceback = (cap.stdout or "") + (cap.stderr or "")
                        attempt_num = _test_healer._attempts + 1
                        console.print(f"  [cyan]🩹 Autoheal: attempting test fix (attempt {attempt_num}/{budget})...[/cyan]")
                        from rich.status import Status
                        with Status(f"  [cyan]🩹 Autoheal: AI healing tests (attempt {attempt_num}/{budget})...[/cyan]", console=console):
                            healed = _test_healer.heal_failure(traceback, cmd, cwd)
                        if healed:
                            console.print(f"  [green]✅ Autoheal fixed {cmd_name}.[/green]")
                        else:
                            console.print(f"  [yellow]⚠️  Autoheal could not fix {cmd_name}.[/yellow]")
                            tests_ok = False
                    else:
                        tests_ok = False
                else:
                    console.print(f"  [green]✅ {cmd_name} passed.[/green]")

            except subprocess.TimeoutExpired:
                console.print(f"  [bold red]❌ {cmd_name} timed out — killed.[/bold red]")
                tests_ok = False
            except Exception as e:
                console.print(f"  [bold red]❌ Failed to execute {cmd_name}: {e}[/bold red]")
                tests_ok = False
    else:
        console.print("\n[dim]No tests selected for current changes.[/dim]")

    if not tests_ok and not ignore_tests:
        if report_file:
            import json
            json_report["overall_verdict"] = "BLOCK"
            json_report["error"] = "Test failure."
            report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)

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

    # 1.7.5 Code Quality Gate (INFRA-106)
    console.print("\n[bold blue]🧹 Checking Code Quality (LOC & Imports)...[/bold blue]")
    quality_result = check_code_quality()
    if not quality_result.passed:
        console.print(f"[bold red]❌ {quality_result.name} FAILED[/bold red]")
        console.print(f"[red]{quality_result.details}[/red]")
        json_report["code_quality"] = "FAIL"
        if report_file:
            json_report["overall_verdict"] = "BLOCK"
            json_report["error"] = quality_result.details
            import json
            report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)
    else:
        console.print(f"[green]✅ {quality_result.name} passed.[/green]")
        console.print(f"[dim]{quality_result.details}[/dim]")
        json_report["code_quality"] = "PASS"

    # 1.8 Journey Coverage Check (Phase 2: Blocking for story-linked journeys)
    from agent.core.check.journeys import check_journey_coverage_gate, run_journey_impact_mapping
    
    console.print("\n[bold blue]📋 Checking Journey Test Coverage...[/bold blue]")
    coverage_result = check_journey_coverage_gate(journey_gate)
    
    if coverage_result["warnings"]:
        console.print(
            f"[yellow]⚠️  Journey Coverage: {coverage_result['linked']}/{coverage_result['total']}"
            f" COMMITTED journeys linked[/yellow]"
        )
        for w in coverage_result["warnings"][:10]:
            console.print(f"  [yellow]• {w}[/yellow]")

    if not coverage_result["passed"]:
        console.print(f"[bold red]❌ {coverage_result['error']}[/bold red]")
        json_report["overall_verdict"] = "BLOCK"
        if report_file:
            import json
            json_report["error"] = coverage_result["error"]
            report_file.write_text(json.dumps(json_report, indent=2))
        raise typer.Exit(code=1)
    else:
        console.print("[green]✅ Journey Coverage: All linked.[/green]")

    # 1.9 Journey Impact Mapping (INFRA-059)
    console.print("\n[bold blue]🗺️  Mapping Changed Files → Journeys...[/bold blue]")
    mapping_result = run_journey_impact_mapping(base)
    
    if mapping_result.get("rebuilt_index"):
        console.print("[dim]  Rebuilt journey index[/dim]")
        
    if mapping_result.get("affected_journeys"):
        affected = mapping_result["affected_journeys"]
        console.print(f"[cyan]  {len(affected)} journey(s) affected by changed files.[/cyan]")
        if mapping_result.get("test_files_to_run"):
            _cmd_str = "pytest " + " ".join(mapping_result["test_files_to_run"])
            console.print(f"  [bold]Run:[/bold] [cyan]{_cmd_str}[/cyan]")
    elif mapping_result.get("changed_files"):
        console.print("[dim]  No journeys affected.[/dim]")
    else:
        console.print("[dim]  No changed files for journey mapping.[/dim]")

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
        # INFRA-138: Write cache so `agent pr` knows preflight passed
        _write_preflight_cache(story_id, "PASS")
        return
        
    console.print(f"[bold blue]🔍 Running preflight checks for {story_id}...[/bold blue]")
    
    # Context Loading
    story_content = ""
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            story_content = file_path.read_text(errors="ignore")
            break
            
            
    # Load full context (rules + instructions + ADRs)
    import asyncio
    full_context = asyncio.run(context_loader.load_context(story_id=story_id, legacy_context=legacy_context))
    rules_content = full_context.get("rules", "")
    instructions_content = full_context.get("instructions", "")
    adrs_content = full_context.get("adrs", "")
    
    # Cap diff size - if larger than chunk limit, we might need a smart splitter, 
    # but for assimilating roles, we send the same diff to each role agent.
    # We'll stick to a reasonable cap for now to fit in context.
    diff_context_lines = "10" if legacy_context else "3" # Oracle Pattern uses -U3 to reduce noise
    diff_cmd = cmd = ["git", "diff", "--cached", f"-U{diff_context_lines}", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", f"-U{diff_context_lines}", "."]
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

        # Healer is created ONCE so the budget is shared across all roles
        # and all governance retry cycles — prevents unbounded token spend.
        _healer = None
        if autoheal:
            from agent.core.preflight.healer import PreflightHealer
            _healer = PreflightHealer(budget=budget)

        for governance_attempt in range(MAX_GOVERNANCE_RETRIES):
            if governance_attempt > 0:
                console.print(f"\n[bold cyan]🔄 Re-running Governance Council (attempt {governance_attempt + 1}/{MAX_GOVERNANCE_RETRIES})...[/bold cyan]")
                
                # Re-compute diff after fix was applied
                diff_cmd = ["git", "diff", "--cached", f"-U{diff_context_lines}", "."] if not base else ["git", "diff", f"origin/{base}...HEAD", f"-U{diff_context_lines}", "."]
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

            console.print("[bold cyan]🤖 Convening AI Governance Council (Running checks)...[/bold cyan]")
            from rich.progress import Progress, SpinnerColumn, TextColumn
            import re
            
            progress = Progress(
                SpinnerColumn(finished_text=" "),
                TextColumn("{task.description}"),
                console=console,
                transient=False
            )
            
            with progress:
                tasks = {}
                try:
                    def _progress(msg: str):
                        msg_stripped = msg.strip()
                        # Start spinner on "is reviewing" — guard against duplicates
                        # from ADK retries sending the same message multiple times.
                        start_match = re.search(r"🤖 @(\w+) is reviewing", msg)
                        if start_match:
                            role = start_match.group(1)
                            if role not in tasks:
                                task_id = progress.add_task(f"[dim]  - {msg_stripped}[/dim]", total=None)
                                tasks[role] = task_id
                            return
                        
                        # Complete spinner on final verdict
                        complete_match = re.search(r"@(\w+):\s*(PASS|BLOCK|CONSULTED)$", msg_stripped)
                        if complete_match and any(x in msg for x in ["✅", "❌", "ℹ️", "⚠️"]):
                            role = complete_match.group(1)
                            if role in tasks:
                                color = "green" if "✅" in msg else "red" if "❌" in msg else "yellow"
                                progress.update(tasks[role], description=f"  [{color}]- {msg_stripped}[/{color}]", completed=100)
                                return
                        
                        # Normal log line
                        progress.console.print(f"[dim]  - {msg_stripped}[/dim]")

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
                        progress_callback=_progress,
                    )
                except Exception as e:
                    console.print(f"\n[bold red]❌ Governance Panel Failed:[/bold red] {e}")
                    if any(ind in str(e).lower() for ind in ["ssl", "certificate_verify", "deadline_exceeded", "504", "deadline expired"]):
                        console.print("[yellow]Hint: Your corporate proxy may be blocking the AI provider or hitting API rate limits/timeouts. Check your VPN/Proxy settings.[/yellow]")
                    raise typer.Exit(code=1)

            # Merge AI report details
            if "json_report" in result:
                 json_report.update(result["json_report"])

            if result["verdict"] not in ["BLOCK", "FAIL"]:
                governance_passed = True
                break  # Council passed — exit the retry loop
            
            # --- BLOCKED: Display findings ---
            from agent.core.check.rendering import handle_blocked_findings
            fix_applied = handle_blocked_findings(console, result, interactive, story_id, config)
            if fix_applied:
                continue

            # Autoheal: extract REQUIRED_CHANGES per blocked role and apply AI fixes
            if _healer:
                if _healer._attempts >= _healer.budget:
                    # Budget fully consumed — no point re-running the panel
                    console.print(f"[yellow]⚠️  Autoheal budget exhausted ({_healer.budget} attempts used). Stopping.[/yellow]")
                    break
                _blocked_roles = [
                    r for r in result.get("json_report", {}).get("roles", [])
                    if r.get("verdict") == "BLOCK"
                ]
                _any_healed = False
                for _role in _blocked_roles:
                    if _healer._attempts >= _healer.budget:
                        break  # Stop iterating roles once budget gone
                    _healed = _healer.heal(
                        role=_role["name"],
                        findings=_role.get("summary", ""),
                        required_changes=_role.get("required_changes") or [],
                        diff=full_diff,
                    )
                    if _healed:
                        _any_healed = True
                        console.print(f"[cyan]🩹 Autoheal applied fix for @{_role['name']} — re-running governance...[/cyan]")
                if _any_healed:
                    continue  # Re-enter governance loop with healed changes

            # If we reach here without a fix applied, break out — no point retrying
            break
        
        # After the loop: check outcome

        # Display Reference Summary Table (INFRA-060 AC-9)
        _ref_metrics = result.get("json_report", {}).get("reference_metrics", {})
        _roles_data = result.get("json_report", {}).get("roles", [])
        _fv_metrics = result.get("json_report", {}).get("finding_validation", {})
        if _ref_metrics.get("total_refs", 0) > 0 or _roles_data:
            _print_reference_summary(console, _roles_data, _ref_metrics, _fv_metrics)

        # Persist per-role verdicts to .preflight_result immediately after the council
        # runs (PASS *and* BLOCK). The next run reads this to inject previous verdicts
        # into the prompt so agents cannot oscillate on already-resolved findings.
        try:
            import json as _json
            import time as _time
            _marker_path = config.cache_dir / ".preflight_result"
            _head_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            ).stdout.strip()
            _overall = result.get("json_report", {}).get("overall_verdict", "UNKNOWN")
            _role_verdicts = {
                r["name"]: {"verdict": r.get("verdict", "UNKNOWN"), "summary": r.get("summary", "")}
                for r in _roles_data
                if "name" in r
            }
            _marker_path.write_text(_json.dumps({
                "story_id": story_id,
                "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
                "commit": _head_sha,
                "verdict": _overall,
                "role_verdicts": _role_verdicts,
            }, indent=2))
        except Exception:
            pass  # Best-effort, non-critical

        if not governance_passed:
            if report_file:
                json_report["overall_verdict"] = "BLOCK"
                json_report["error"] = "Preflight blocked by governance checks."
                import json
                report_file.write_text(json.dumps(json_report, indent=2))

            raise typer.Exit(code=1)

        # Detect when all agents failed (e.g. auth expired) — all findings
        # were filtered with 0 validated, meaning no agent actually reviewed
        _fv_check = result.get("json_report", {}).get("finding_validation", {})
        _total_ai = _fv_check.get("total_ai_findings", 0)
        _validated = _fv_check.get("validated", 0)
        _filtered = _fv_check.get("filtered_false_positives", 0)
        if _total_ai > 0 and _validated == 0 and _filtered == _total_ai:
            _obs_logger = get_logger(__name__)
            from agent.core.ai import ai_service as _ai_svc
            _provider = getattr(_ai_svc, "provider", None) or "unknown"
            _obs_logger.warning(
                "Preflight inconclusive: all governance agents failed",
                extra={"provider": _provider, "total_findings": _total_ai},
            )
            console.print(
                "[bold yellow]⚠️  Preflight INCONCLUSIVE — all governance agents failed "
                "(likely due to expired credentials). No checks were actually performed.[/bold yellow]"
            )
            # Provider-aware credential hint
            _auth_hints = {
                "gemini": "Run [bold]agent secret set GEMINI_API_KEY[/bold] or check your API key.",
                "vertex": "Run [bold]gcloud auth application-default login[/bold] to reauthenticate.",
                "openai": "Run [bold]agent secret set OPENAI_API_KEY[/bold] or check your API key.",
                "anthropic": "Run [bold]agent secret set ANTHROPIC_API_KEY[/bold] or check your API key.",
                "ollama": "Ensure Ollama is running locally ([bold]ollama serve[/bold]).",
                "gh": "Run [bold]gh auth login[/bold] to reauthenticate.",
            }
            _hint = _auth_hints.get(_provider, "Check your AI provider credentials.")
            console.print(
                f"[yellow]{_hint} Then re-run [bold]agent preflight[/bold].[/yellow]"
            )
            if report_file:
                json_report["overall_verdict"] = "INCONCLUSIVE"
                json_report["error"] = "All governance agents failed — no checks performed."
                import json
                report_file.write_text(json.dumps(json_report, indent=2))
            raise typer.Exit(code=1)
    
    _preflight_duration_ms = int((_pf_time.time() - _preflight_start) * 1000)
    logger.info(
        "preflight_timing",
        extra={
            "story_id": story_id,
            "duration_ms": _preflight_duration_ms,
            "verdict": "PASS",
        },
    )

    console.print(
        f"[bold green]✅ Preflight checks passed![/bold green] "
        f"[dim]({_preflight_duration_ms}ms)[/dim]"
    )

    # INFRA-138: Always write cache on successful completion so `agent pr`
    # can detect the pass without re-running preflight.
    _write_preflight_cache(story_id, "PASS")

    if report_file:
         import json
         # Ensure we have a verdict if we skipped AI or it passed
         if json_report["overall_verdict"] == "UNKNOWN":
             json_report["overall_verdict"] = "PASS"
             
         report_file.write_text(json.dumps(json_report, indent=2))





# nolint: loc-ceiling
