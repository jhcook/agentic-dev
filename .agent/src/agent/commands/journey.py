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

import logging
import re
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import IntPrompt, Prompt

from agent.core.config import config
from agent.core.utils import sanitize_title
from agent.db.client import upsert_artifact

app = typer.Typer()
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
    ai: bool = typer.Option(
        False, "--ai", help="Use AI to generate journey content from a description."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, openai)."
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
    if ai:
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
                        "[yellow]⚠️  AI output was not valid YAML. Using template instead.[/yellow]"
                    )
        except Exception as e:
            console.print(f"[yellow]⚠️  AI generation failed: {e}. Using template.[/yellow]")

    # Write file
    file_path.write_text(content)
    logger.info("journey_created", extra={"journey_id": journey_id, "scope": scope, "path": str(file_path)})
    console.print(f"[bold green]✅ Created journey: {file_path}[/bold green]")

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
