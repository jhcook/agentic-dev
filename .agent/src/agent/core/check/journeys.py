# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0 (the "License");

import subprocess
import sqlite3
import typer
from rich.console import Console
from agent.core.config import config
from agent.core.logger import get_logger

logger = get_logger(__name__)

def check_journey_coverage_gate(console: Console, journey_gate: dict, json_report: dict, report_file) -> None:
    """Run Phase 2 of Journey Coverage Check (Blocking for story-linked journeys)."""
    console.print("\n[bold blue]📋 Checking Journey Test Coverage...[/bold blue]")
    from agent.core.check.quality import check_journey_coverage
    
    coverage_result = check_journey_coverage()
    json_report["journey_coverage"] = coverage_result

    if coverage_result["warnings"]:
        console.print(
            f"[yellow]⚠️  Journey Coverage: {coverage_result['linked']}/{coverage_result['total']}"
            f" COMMITTED journeys linked[/yellow]"
        )
        for w in coverage_result["warnings"][:10]:  # Cap output
            console.print(f"  [yellow]• {w}[/yellow]")

        # Block if any journey linked to THIS story has missing tests
        story_journey_ids = set(journey_gate.get("journey_ids", []))
        missing_ids = set(coverage_result.get("missing_ids", []))
        blocked_journeys = story_journey_ids & missing_ids

        if blocked_journeys:
            msg = (
                f"Journey Test Coverage FAILED — story-linked journey(s) "
                f"{', '.join(sorted(blocked_journeys))} have no tests. "
                f"Add tests to implementation.tests in each journey YAML."
            )
            console.print(f"[bold red]❌ {msg}[/bold red]")
            json_report["overall_verdict"] = "BLOCK"
            if report_file:
                import json
                json_report["error"] = msg
                report_file.write_text(json.dumps(json_report, indent=2))
            raise typer.Exit(code=1)
    else:
        console.print("[green]✅ Journey Coverage: All linked.[/green]")


def run_journey_impact_mapping(console: Console, base: str | None, json_report: dict) -> None:
    """Map changed files to journeys (INFRA-059)."""
    console.print("\n[bold blue]🗺️  Mapping Changed Files → Journeys...[/bold blue]")
    from agent.db.journey_index import (
        get_affected_journeys as _get_affected,
        is_stale as _is_stale,
        rebuild_index as _rebuild_idx,
    )
    from agent.db.init import get_db_path as _get_db_path

    _db = sqlite3.connect(_get_db_path())
    _journeys_dir = config.journeys_dir
    _repo_root = config.repo_root

    if _is_stale(_db, _journeys_dir):
        _idx = _rebuild_idx(_db, _journeys_dir, _repo_root)
        logger.info("Rebuilt journey index", extra={"index": _idx})
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
    try:
        _pf_res = subprocess.run(_pf_cmd, capture_output=True, text=True)
        _pf_files = _pf_res.stdout.strip().splitlines()
        _pf_files = [f for f in _pf_files if f]
    except Exception as e:
        logger.error("Failed to get git diff", extra={"error": str(e)})
        _pf_files = []

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
