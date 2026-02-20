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

import json as json_mod
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import typer
import yaml
from rich.console import Console
from rich.prompt import IntPrompt, Prompt

from agent.core.config import config
from agent.core.utils import sanitize_title
from agent.db.client import upsert_artifact

app = typer.Typer(help="User journey management.")
console = Console()
logger = logging.getLogger(__name__)


def _get_next_journey_id(scope_dir: Path, prefix: str) -> str:
    """
    Finds the next available journey ID within a scope directory.
    Journey IDs use the JRN-XXX format.
    """
    from agent.db.client import get_connection

    max_num = 0
    pattern = re.compile(r"JRN-(\d+)")

    # A. Scan filesystem — check all scope dirs under journeys_dir
    if config.journeys_dir.exists():
        for file_path in config.journeys_dir.rglob("JRN-*.yaml"):
            match = pattern.search(file_path.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

    # B. Scan database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM artifacts WHERE id LIKE 'JRN-%'")
        rows = cursor.fetchall()
        for row in rows:
            match = pattern.search(row[0])
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        conn.close()
    except Exception as e:
        console.print(f"[yellow]⚠️  DB check failed for journey ID generation: {e}[/yellow]")

    next_num = max_num + 1
    return f"JRN-{next_num:03d}"


def new_journey(
    journey_id: Optional[str] = typer.Argument(
        None, help="The ID of the journey (e.g., JRN-001). Auto-generated if omitted."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Disable AI and use manual input for journey content."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)."
    ),
):
    """
    Create a new user journey YAML file.
    """
    # Scope selection (journeys use scope dirs for organization)
    console.print("Select Journey Scope:")
    console.print("1. WEB (Frontend)")
    console.print("2. MOBILE (React Native)")
    console.print("3. BACKEND (FastAPI)")
    console.print("4. INFRA (Governance, CI/CD)")

    choice = IntPrompt.ask("Choice", choices=["1", "2", "3", "4"])
    prefixes = {1: "WEB", 2: "MOBILE", 3: "BACKEND", 4: "INFRA"}
    scope = prefixes[choice]

    scope_dir = config.journeys_dir / scope
    scope_dir.mkdir(parents=True, exist_ok=True)

    if not journey_id:
        journey_id = _get_next_journey_id(scope_dir, "JRN")
        console.print(f"🛈 Auto-assigning ID: [bold cyan]{journey_id}[/bold cyan]")

    title = Prompt.ask("Enter Journey Title")
    safe_title = sanitize_title(title)
    filename = f"{journey_id}-{safe_title}.yaml"
    file_path = scope_dir / filename

    if file_path.exists():
        console.print(
            f"[bold red]❌ Journey {journey_id} already exists at {file_path}[/bold red]"
        )
        raise typer.Exit(code=1)

    # Load template
    template_path = config.templates_dir / "journey-template.yaml"

    if template_path.exists():
        content = template_path.read_text()
        content = content.replace("JRN-XXX", journey_id)
        content = content.replace("<Title>", title)
    else:
        # Fallback template
        content = f"""# Journey: {journey_id}
# Title: {title}
# State: DRAFT

actor: "<user persona>"
description: "<what this journey achieves>"

steps:
  - action: "<user action>"
    system_response: "<expected system behavior>"
    assertions:
      - "<verifiable outcome>"

acceptance_criteria:
  - "<criterion 1>"

linked_stories: []
linked_adrs: []
"""

    # AI-assisted content generation
    if offline:
        # Prompt for manual entry via editor
        console.print("[dim]Opening editor for manual journey creation...[/dim]")
        edited_content = typer.edit(text=content)
        if edited_content:
            content = edited_content
    else:
        console.print("[bold blue]🤖 AI-assisted journey generation...[/bold blue]")
        description = Prompt.ask(
            "Describe the user journey in a few sentences"
        )

        try:
            from agent.core.ai import ai_service  # ADR-025: lazy init
            from agent.core.utils import scrub_sensitive_data

            if provider:
                ai_service.set_provider(provider)

            # Load existing journeys for context
            existing_journeys = ""
            if config.journeys_dir.exists():
                for jf in config.journeys_dir.rglob("*.yaml"):
                    existing_journeys += f"\n---\n{jf.read_text()}"

            system_prompt = """You are a User Journey Designer.
Generate a structured YAML user journey based on the user's description.

OUTPUT FORMAT:
Return ONLY valid YAML content (no markdown fences). Use the exact structure shown in the template.
Fill in realistic values for all fields. Include 3-5 steps, 2-3 acceptance criteria,
at least 1 error path, and at least 1 edge case.

IMPORTANT:
- Use yaml.safe_load compatible syntax only.
- Strings with special characters must be quoted.
- Keep assertions concrete and testable.
"""

            user_prompt = f"""TEMPLATE STRUCTURE:
{scrub_sensitive_data(content)}

JOURNEY DESCRIPTION:
{scrub_sensitive_data(description)}

JOURNEY ID: {journey_id}
JOURNEY TITLE: {title}

EXISTING JOURNEYS (for context, avoid duplication):
{scrub_sensitive_data(existing_journeys[:3000]) if existing_journeys else "None yet."}

Generate the journey YAML now.
"""

            with console.status("[bold green]🤖 AI is designing the journey...[/bold green]"):
                ai_content = ai_service.complete(system_prompt, user_prompt)

            if ai_content:
                # Validate the AI output is valid YAML
                try:
                    yaml.safe_load(ai_content)
                    content = ai_content
                    console.print("[bold green]✅ AI generated valid journey content[/bold green]")
                except yaml.YAMLError:
                    console.print(
                        "[yellow]⚠️  AI output was not valid YAML. Falling back to editor.[/yellow]"
                    )
                    edited_content = typer.edit(text=ai_content)
                    if edited_content:
                        content = edited_content
        except Exception as e:
            console.print(f"[yellow]⚠️  AI generation failed. Falling back to manual input.[/yellow]")
            edited_content = typer.edit(text=content)
            if edited_content:
                content = edited_content

    # Write file
    file_path.write_text(content)
    logger.info("journey_created", extra={"journey_id": journey_id, "scope": scope, "path": str(file_path)})
    console.print(f"[bold green]✅ Created journey: {file_path}[/bold green]")

    # Prompt to link test files (INFRA-058)
    test_paths_input = Prompt.ask(
        "[bold]Link test files? [comma-separated paths or Enter to generate stub][/bold]",
        default="",
    )
    if test_paths_input.strip():
        linked_paths = [p.strip() for p in test_paths_input.split(",")]
    else:
        slug = journey_id.lower().replace("-", "_")
        stub_dir = config.repo_root / "tests" / "journeys"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub_path = stub_dir / f"test_{slug}.py"
        if not stub_path.exists():
            stub_path.write_text(
                f'"""Auto-generated stub for {journey_id}."""\n'
                "import pytest\n\n\n"
                f'@pytest.mark.journey("{journey_id}")\n'
                f"def test_{slug}():\n"
                '    pytest.skip("Not yet implemented")\n'
            )
            console.print(f"[green]📝 Generated test stub: {stub_path}[/green]")
        linked_paths = [str(stub_path.relative_to(config.repo_root))]

    # Update the journey YAML with test paths
    data = yaml.safe_load(file_path.read_text())
    if not isinstance(data, dict):
        data = {}
    if "implementation" not in data:
        data["implementation"] = {}
    data["implementation"]["tests"] = linked_paths
    file_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    # Auto-sync to local DB
    if upsert_artifact(journey_id, "journey", content, author="agent"):
        console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
        console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    # Auto-sync to providers
    from agent.sync.sync import push_safe

    console.print("[dim]Syncing to configured providers (Notion/Supabase)...[/dim]")
    push_safe(timeout=2, verbose=True, artifact_id=journey_id)


def validate_journey(
    journey_path: str = typer.Argument(..., help="Path to the journey YAML file."),
):
    """
    Validate a journey YAML file against the schema.
    """
    file_path = Path(journey_path)

    if not file_path.exists():
        console.print(f"[bold red]❌ File not found: {journey_path}[/bold red]")
        raise typer.Exit(code=1)

    try:
        content = file_path.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        console.print(f"[bold red]❌ Invalid YAML: {e}[/bold red]")
        raise typer.Exit(code=1)

    if not isinstance(data, dict):
        console.print("[bold red]❌ Journey must be a YAML mapping (dict)[/bold red]")
        raise typer.Exit(code=1)

    # Required fields validation
    errors = []
    warnings = []

    required_fields = ["actor", "description", "steps"]
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: '{field}'")

    # Steps validation
    if "steps" in data and isinstance(data["steps"], list):
        for i, step in enumerate(data["steps"]):
            if not isinstance(step, dict):
                errors.append(f"Step {i + 1}: must be a mapping")
                continue
            if "action" not in step:
                errors.append(f"Step {i + 1}: missing 'action'")
            if "system_response" not in step:
                warnings.append(f"Step {i + 1}: missing 'system_response'")
            if "assertions" not in step or not step.get("assertions"):
                warnings.append(f"Step {i + 1}: no assertions defined")

    # Optional but recommended fields
    recommended = ["acceptance_criteria", "error_paths", "edge_cases"]
    for field in recommended:
        if field not in data or not data[field]:
            warnings.append(f"Recommended field missing or empty: '{field}'")

    # State-aware test enforcement (INFRA-058: AC-1, AC-2, AC-7)
    state = (data.get("state") or "DRAFT").upper()
    impl_tests = data.get("implementation", {}).get("tests", [])

    if state in ("COMMITTED", "ACCEPTED"):
        if not impl_tests:
            errors.append(
                "COMMITTED/ACCEPTED journey requires non-empty 'implementation.tests'"
            )
        else:
            for test_path_str in impl_tests:
                test_path = Path(test_path_str)
                # Reject absolute paths
                if test_path.is_absolute():
                    errors.append(f"Test path must be relative: '{test_path_str}'")
                    continue
                # Reject path traversal
                try:
                    resolved = (config.repo_root / test_path).resolve()
                    resolved.relative_to(config.repo_root.resolve())
                except ValueError:
                    errors.append(
                        f"Test path escapes project root: '{test_path_str}'"
                    )
                    continue
                # Check file exists (extension-agnostic)
                if not resolved.exists():
                    errors.append(f"Test file not found: '{test_path_str}'")

    # Report
    if errors:
        logger.warning("journey_validation_failed", extra={"path": journey_path, "errors": errors})
        console.print("[bold red]❌ Validation FAILED:[/bold red]")
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
        for warn in warnings:
            console.print(f"  [yellow]• {warn}[/yellow]")
        raise typer.Exit(code=1)

    if warnings:
        console.print("[bold green]✅ Valid[/bold green] (with warnings):")
        for warn in warnings:
            console.print(f"  [yellow]• {warn}[/yellow]")
    else:
        logger.info("journey_validated", extra={"path": journey_path})
        console.print("[bold green]✅ Journey is valid and complete[/bold green]")


@app.command()
def coverage(
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON for CI."
    ),
    scope: Optional[str] = typer.Option(
        None, "--scope", help="Filter by scope (INFRA, MOBILE, WEB, BACKEND)."
    ),
) -> None:
    """Report journey → test mapping with coverage status."""
    journeys_dir = config.journeys_dir
    if not journeys_dir.exists():
        console.print("[yellow]No journeys directory found.[/yellow]")
        raise typer.Exit(0)

    results: List[Dict[str, Any]] = []
    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        if scope and scope_dir.name.upper() != scope.upper():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            j_state = (data.get("state") or "DRAFT").upper()
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)
            title = data.get("title", "")

            statuses: List[Dict[str, Any]] = []
            for t in tests:
                resolved = (config.repo_root / t).resolve()
                statuses.append({"path": t, "exists": resolved.exists()})

            if not tests:
                overall = "❌ No tests"
            elif all(s["exists"] for s in statuses):
                overall = "✅ Linked"
            else:
                overall = "⚠️ Missing"

            results.append({
                "id": jid,
                "title": title,
                "state": j_state,
                "tests": len(tests),
                "status": overall,
                "details": statuses,
            })

    if json_output:
        console.print_json(json_mod.dumps(results))
        return

    from rich.table import Table

    table = Table(title="Journey Test Coverage")
    table.add_column("Journey ID", style="cyan")
    table.add_column("Title")
    table.add_column("State")
    table.add_column("Tests", justify="right")
    table.add_column("Status")
    for r in results:
        table.add_row(
            r["id"], str(r["title"])[:40], r["state"],
            str(r["tests"]), r["status"],
        )
    console.print(table)

    linked = sum(1 for r in results if "✅" in r["status"])
    total = sum(1 for r in results if r["state"] in ("COMMITTED", "ACCEPTED"))
    pct = (linked / total * 100) if total else 0
    console.print(
        f"\nCoverage: {linked}/{total} COMMITTED+ journeys linked ({pct:.0f}%)"
    )


# -- License header for AI-generated test files --
_LICENSE_HEADER = """\
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

_MAX_SOURCE_CHARS = 32_000  # ~8k tokens

logger = logging.getLogger(__name__)


class EligibleJourney(TypedDict):
    """Typed structure for an eligible journey record."""
    file: Path
    data: Dict[str, Any]
    jid: str


def _iter_eligible_journeys(
    journeys_dir: Path,
    scope: Optional[str] = None,
    journey_id: Optional[str] = None,
) -> List[EligibleJourney]:
    """Return list of dicts with 'file', 'data', 'jid' for eligible journeys.

    Eligible = COMMITTED state and no tests already defined.
    """
    results: List[EligibleJourney] = []
    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        if scope and scope_dir.name.upper() != scope.upper():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            jid = data.get("id", jfile.stem)
            if journey_id and jid != journey_id:
                continue
            j_state = (data.get("state") or "DRAFT").upper()
            tests = data.get("implementation", {}).get("tests", [])
            if j_state != "COMMITTED" or tests:
                continue
            results.append({"file": jfile, "data": data, "jid": jid})
    return results


def _generate_stub(data: dict, jid: str) -> str:
    """Generate a pytest stub from journey assertions."""
    slug = jid.lower().replace("-", "_")
    steps = data.get("steps", [])
    test_funcs: List[str] = []
    for i, step in enumerate(steps, 1):
        assertions = (
            step.get("assertions", []) if isinstance(step, dict) else []
        )
        assertion_comments = (
            "\n".join(f"    # {a}" for a in assertions)
            if assertions
            else "    # No assertions defined"
        )
        action_str = (
            step.get("action", "unnamed")[:60]
            if isinstance(step, dict)
            else "unnamed"
        )
        test_funcs.append(
            f'\n@pytest.mark.journey("{jid}")\n'
            f"def test_{slug}_step_{i}():\n"
            f'    """Step {i}: {action_str}"""\n'
            f"{assertion_comments}\n"
            '    pytest.skip("Not yet implemented")\n'
        )
    return (
        f'"""Auto-generated test stubs for {jid}."""\n'
        "import pytest\n" + "".join(test_funcs)
    )


def _generate_ai_test(
    data: dict,
    jid: str,
    repo_root: Path,
) -> Optional[str]:
    """Generate a pytest test using the AI service.

    Returns generated test code on success, None on failure
    (caller falls back to stub).

    GDPR Lawful Basis (Art. 6(1)(f) — Legitimate Interest):
    This function processes *source code* (not personal data) to generate
    test scaffolding.  All input is scrubbed by ``scrub_sensitive_data``
    before submission to the AI service.  No PII is collected, stored,
    or transmitted.
    """
    import ast
    import time

    from agent.core.ai import ai_service  # ADR-025: lazy init
    from agent.core.security import scrub_sensitive_data

    start = time.monotonic()
    steps = data.get("steps", [])
    if not steps:
        logger.warning(
            "journey=%s | No steps defined, skipping AI generation", jid
        )
        return None

    # Build source context from implementation.files
    impl_files = data.get("implementation", {}).get("files", [])
    source_context = ""
    for rel_path in impl_files:
        fpath = repo_root / rel_path
        if not fpath.is_file():
            logger.warning(
                "journey=%s | Source file not found: %s", jid, rel_path
            )
            continue
        # Path containment check
        try:
            fpath.resolve().relative_to(repo_root.resolve())
        except ValueError:
            logger.warning(
                "journey=%s | Path escapes repo root: %s", jid, rel_path
            )
            continue
        try:
            raw = fpath.read_text(errors="replace")[:20_000]
            scrubbed = scrub_sensitive_data(raw)
            source_context += f"\n--- {rel_path} ---\n{scrubbed}"
        except Exception:
            logger.warning(
                "journey=%s | Error reading %s", jid, rel_path, exc_info=True
            )

    # Truncate to token budget
    if len(source_context) > _MAX_SOURCE_CHARS:
        source_context = source_context[:_MAX_SOURCE_CHARS]

    # Build prompt
    from agent.core.ai.prompts import generate_test_prompt

    system_prompt, user_prompt = generate_test_prompt(
        data, jid, source_context
    )

    # Call AI service
    try:
        response = ai_service.complete(system_prompt, user_prompt)
    except Exception:
        logger.exception("journey=%s | AI service call failed", jid)
        return None

    if not response:
        logger.warning("journey=%s | AI returned empty response", jid)
        return None

    # Strip markdown code fences if present
    if response.startswith("```"):
        lines = response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines)

    # Validate generated code with ast.parse (never exec/eval)
    try:
        ast.parse(response)
    except SyntaxError as e:
        logger.warning(
            "journey=%s | AI output has syntax error: %s", jid, e
        )
        return None

    duration = time.monotonic() - start
    scope_name = data.get("scope", "UNKNOWN")
    logger.info(
        "journey=%s | scope=%s | chars=%d | duration_s=%.1f | status=success",
        jid,
        scope_name,
        len(source_context),
        duration,
    )

    slug = jid.lower().replace("-", "_")
    return (
        _LICENSE_HEADER
        + f'"""AI-generated regression tests for {jid}."""\n'
        + response
    )


@app.command("backfill-tests")
def backfill_tests(
    scope: Optional[str] = typer.Option(
        None, "--scope", help="Filter by scope."
    ),
    journey_id: Optional[str] = typer.Option(
        None, "--journey", help="Target single journey (JRN-XXX)."
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Disable AI test generation (local stub only).",
    ),
    write: bool = typer.Option(
        False, "--write", help="Batch-write all without prompts (CI mode)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview only, no prompts, no writes."
    ),
) -> None:
    """Generate pytest test stubs for COMMITTED journeys with empty tests."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax

    journeys_dir = config.journeys_dir
    tests_dir = config.repo_root / "tests" / "journeys"

    if not dry_run:
        tests_dir.mkdir(parents=True, exist_ok=True)

    eligible = _iter_eligible_journeys(journeys_dir, scope, journey_id)
    if not eligible:
        if not offline:
            console.print("[yellow]No eligible journeys found.[/yellow]")
        else:
            verb = "Would generate" if dry_run else "Generated"
            console.print(f"\n{verb} 0 test stub(s)")
        return

    ai_successes = 0
    fallbacks = 0
    skips = 0
    errors = 0
    written = 0
    write_all = False  # Tracks "all" response in interactive mode

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            "[cyan]Processing journeys...", total=len(eligible)
        )

        for entry in eligible:
            jfile = entry["file"]
            data = entry["data"]
            jid = entry["jid"]
            slug = jid.lower().replace("-", "_")
            stub_path = tests_dir / f"test_{slug}.py"

            progress.update(task, description=f"[cyan]{jid}...")

            if stub_path.exists():
                logger.info("journey=%s | skipped=file_exists", jid)
                skips += 1
                progress.update(task, advance=1)
                continue

            # Generate content
            content: Optional[str] = None
            used_ai = False

            if not offline:
                try:
                    content = _generate_ai_test(
                        data, jid, config.repo_root
                    )
                    if content:
                        used_ai = True
                        ai_successes += 1
                    else:
                        # Fallback to stub
                        content = _generate_stub(data, jid)
                        fallbacks += 1
                except Exception:
                    logger.exception(
                        "journey=%s | AI generation error", jid
                    )
                    content = _generate_stub(data, jid)
                    fallbacks += 1
                    errors += 1
            else:
                content = _generate_stub(data, jid)

            if not content:
                errors += 1
                progress.update(task, advance=1)
                continue

            # Determine output mode
            if dry_run:
                progress.stop()
                if not offline:
                    label = "AI-generated" if used_ai else "Stub"
                    console.print(
                        f"\n[bold]{label} test for {jid}[/bold] → {stub_path}"
                    )
                    console.print(
                        Syntax(content, "python", theme="monokai", line_numbers=True)
                    )
                else:
                    console.print(f"[dim]Would create: {stub_path}[/dim]")
                written += 1
                progress.start()
                progress.update(task, advance=1)
                continue

            if not offline and not write and not write_all:
                # Interactive confirm mode
                progress.stop()
                label = "AI-generated" if used_ai else "Stub (AI fallback)"
                console.print(
                    f"\n[bold]{label} test for {jid}[/bold] → {stub_path}"
                )
                console.print(
                    Syntax(content, "python", theme="monokai", line_numbers=True)
                )
                choice = Prompt.ask(
                    "Write?",
                    choices=["y", "n", "all", "skip"],
                    default="n",
                )
                progress.start()

                if choice == "n":
                    skips += 1
                    progress.update(task, advance=1)
                    continue
                elif choice == "skip":
                    skips += 1
                    break
                elif choice == "all":
                    write_all = True
                # choice == "y" or write_all: fall through to write

            # Write file
            stub_path.parent.mkdir(parents=True, exist_ok=True)
            stub_path.write_text(content)

            # Update journey YAML with test path
            if "implementation" not in data:
                data["implementation"] = {}
            data["implementation"]["tests"] = [
                str(stub_path.relative_to(config.repo_root))
            ]
            jfile.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False)
            )

            logger.info("journey=%s | written=%s", jid, stub_path)
            console.print(f"[green]✅ Generated: {stub_path}[/green]")
            written += 1
            progress.update(task, advance=1)

    # Summary metrics
    total = len(eligible)
    if not offline:
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total processed: {total}")
        console.print(f"  Written:         {written}")
        console.print(f"  AI successes:    {ai_successes}")
        console.print(f"  AI fallbacks:    {fallbacks}")
        console.print(f"  Skipped:         {skips}")
        console.print(f"  Errors:          {errors}")
    else:
        verb = "Would generate" if dry_run else "Generated"
        console.print(f"\n{verb} {written} test stub(s)")
