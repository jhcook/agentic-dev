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

"""CLI command for reviewing the most recent voice agent session.

GDPR Lawful Basis: Art. 6(1)(f) — legitimate interest for UX improvement.
Session data is scrubbed before AI submission.
"""

import json
import logging
import subprocess
import time
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from agent.core.config import config

logger = logging.getLogger(__name__)
console = Console()

REVIEW_PROMPT = """You are a Voice UX Analyst reviewing a voice agent session transcript.

Analyze the following session for quality across these categories:

1. **Latency**: Did the user have to repeat themselves? Were there long pauses or timeouts?
2. **Accuracy**: Did the agent misunderstand the user's intent? Were responses factually correct?
3. **Tone**: Was the agent helpful and concise (per the system prompt guidelines)? Was it natural?
4. **Interruption**: Did the agent interrupt the user inappropriately? Were turn-taking signals handled well?

For each category, provide:
- A rating: EXCELLENT / GOOD / NEEDS IMPROVEMENT / POOR
- Specific examples from the transcript supporting your rating
- Concrete recommendations for improvement

Finally, provide:
- An overall session quality rating
- Up to 3 specific recommendations for changes to `voice_system_prompt.txt` or `voice.yaml` config

Format your response as structured sections with clear headings.

## Session Transcript

{session_content}
"""


def review_voice(
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output raw AI response as JSON for CI integration."
    ),
):
    """
    Review the most recent voice agent session with AI-powered UX analysis.

    Fetches the last voice session via fetch_last_session.py, sends
    it to AI for analysis across latency, accuracy, tone, and
    interruption categories, and outputs structured UX feedback.
    """
    # Locate the fetch script
    script_path = config.repo_root / ".agent" / "scripts" / "fetch_last_session.py"
    if not script_path.exists():
        console.print(
            "[bold red]❌ fetch_last_session.py not found at "
            f"{script_path}[/bold red]"
        )
        console.print(
            "[dim]Ensure .agent/scripts/fetch_last_session.py exists.[/dim]"
        )
        raise typer.Exit(code=1)

    # Fetch the session
    console.print("[bold blue]🎙️  Fetching last voice session...[/bold blue]")
    start_time = time.time()

    try:
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(config.repo_root),
        )
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠️  Session fetch timed out after 10s[/yellow]")
        raise typer.Exit(code=0)
    except FileNotFoundError:
        console.print("[bold red]❌ python3 not found in PATH[/bold red]")
        raise typer.Exit(code=1)

    session_content = result.stdout.strip()

    # Check for empty or error results
    if not session_content:
        console.print("[yellow]No active voice session found.[/yellow]")
        raise typer.Exit(code=0)

    # Try to parse as JSON to check for error responses
    try:
        parsed = json.loads(session_content)
        if isinstance(parsed, dict) and "error" in parsed:
            console.print(
                f"[yellow]No active session: {parsed['error']}[/yellow]"
            )
            raise typer.Exit(code=0)
    except json.JSONDecodeError:
        pass  # Not JSON — treat as raw transcript

    session_chars = len(session_content)
    logger.info(
        "voice_session_fetched",
        extra={"session_chars": session_chars},
    )
    console.print(
        f"[dim]Session loaded ({session_chars:,} chars)[/dim]"
    )

    # Scrub sensitive data before AI submission
    from agent.core.security import scrub_sensitive_data

    scrubbed_content = scrub_sensitive_data(session_content)

    # Set provider if specified
    if provider:
        from agent.core.ai import ai_service

        ai_service.set_provider(provider)

    # Build prompt and run AI analysis
    console.print("[bold blue]🤖 Analyzing session...[/bold blue]")
    analysis_start = time.time()

    from agent.core.ai import ai_service

    prompt = REVIEW_PROMPT.format(session_content=scrubbed_content[:50000])

    try:
        analysis = ai_service.complete(prompt)
    except Exception as e:
        console.print(
            f"[bold red]❌ AI analysis failed: {e}[/bold red]"
        )
        logger.warning(
            "voice_analysis_failed",
            extra={"error": str(e)},
        )
        raise typer.Exit(code=1)

    analysis_duration = time.time() - analysis_start
    logger.info(
        "voice_analysis_complete",
        extra={
            "session_chars": session_chars,
            "analysis_duration_s": round(analysis_duration, 2),
            "provider": provider or "default",
        },
    )

    # Output results
    if json_output:
        output = json.dumps(
            {
                "session_chars": session_chars,
                "analysis_duration_s": round(analysis_duration, 2),
                "analysis": analysis,
            },
            indent=2,
        )
        typer.echo(output)
    else:
        total_duration = time.time() - start_time
        console.print()
        console.print(
            Panel(
                analysis,
                title="🎙️ Voice Session Review",
                border_style="blue",
            )
        )
        console.print()
        console.print(
            f"[dim]Analysis completed in {analysis_duration:.1f}s "
            f"(total: {total_duration:.1f}s)[/dim]"
        )
