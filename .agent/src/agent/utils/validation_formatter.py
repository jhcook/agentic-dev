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
Formatting utilities for Pydantic validation errors in runbooks.

This module is part of the CLI schema validation gate (INFRA-149). When a
runbook fails Pydantic schema validation, the raw error list is passed to
:func:`format_runbook_errors` which produces human-readable, Rich-compatible
output for immediate display in the terminal.  It handles plain string
errors, Pydantic ``ErrorDict`` structures (with ``loc`` / ``msg`` fields),
and gracefully falls back for unexpected types.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.panel import Panel

def format_runbook_errors(errors: List[Dict[str, Any]]) -> str:
    """Formats runbook validation errors into a human-readable string."""
    if not errors:
        return ""

    lines = ["### SCHEMA VALIDATION FAILED ###"]

    for i, err in enumerate(errors, 1):
        if isinstance(err, str):
            lines.append(f"{i}. {err}")
        elif isinstance(err, dict):
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Unknown error")

            step_marker = ""
            if "steps" in err.get("loc", []):
                for p in err.get("loc", []):
                    if isinstance(p, int):
                        step_marker = f" (Step {p + 1})"
                        break

            lines.append(f"{i}. [bold red]{loc}[/bold red]{step_marker}: {msg}")
        else:
            lines.append(f"{i}. {str(err)}")

    return "\n".join(lines)

def format_projected_syntax_error(
    file_path: Path,
    error_msg: str,
    line: Optional[int],
) -> str:
    """
    Format a projected SyntaxError for the AI correction prompt.

    Sanitizes paths to protect sensitive metadata and provides explicit tips.
    """
    rel_file = file_path.name
    line_info = f" at line {line}" if line is not None else ""
    return (
        f"Gate 3.5 Failure: Your [MODIFY] block for {rel_file} produces invalid Python "
        f"syntax{line_info}. Error: {error_msg}. "
        "Re-emit the complete, syntactically valid REPLACE block with correct indentation "
        "and balanced brackets."
    )


def format_implementation_summary(
    applied_files: List[str],
    warned_files: Dict[str, List[str]],
    rejected_files: List[str]
) -> Panel:
    """
    Creates a formatted summary panel for the 'agent implement' command.

    Handles three distinct states:
    1. SUCCESS: No rejections, no warnings.
    2. SUCCESS WITH WARNINGS: No rejections, but documentation warnings occurred.
    3. INCOMPLETE IMPLEMENTATION: One or more files were rejected.
    """
    if rejected_files:
        title = "[bold red]INCOMPLETE IMPLEMENTATION[/bold red]"
        border_style = "red"
    elif warned_files:
        title = "[bold yellow]SUCCESS WITH WARNINGS[/bold yellow]"
        border_style = "yellow"
    else:
        title = "[bold green]SUCCESS[/bold green]"
        border_style = "green"

    output = []
    if applied_files:
        output.append(f"[bold green]✓ Applied Files:[/bold green] {len(applied_files)}")

    if warned_files:
        output.append("\n[bold yellow]! Files Persisted with Warnings:[/bold yellow]")
        for file_path, issues in warned_files.items():
            output.append(f"  • [cyan]{file_path}[/cyan]")
            for issue in issues:
                output.append(f"    [dim]- {issue}[/dim]")

    if rejected_files:
        output.append("\n[bold red]× Rejected Files (Not Applied):[/bold red]")
        for file_path in rejected_files:
            output.append(f"  • [red]{file_path}[/red]")

    return Panel(
        "\n".join(output),
        title=title,
        border_style=border_style,
        padding=(1, 2),
        expand=False
    )
