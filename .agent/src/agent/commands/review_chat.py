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

"""CLI command for reviewing the most recent agent console session.

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

REVIEW_PROMPT = """You are an Agentic Dev Tools UX Analyst reviewing an agent console session transcript.

Analyze the following session for quality across these categories:

1. **Accuracy**: Did the agent correctly interpret the user's intent? Were responses factually correct and directly helpful?
2. **Tool Usage**: Did the agent correctly use tools to discover context before answering? Was tool use efficient, or did it hallucinate answers instead of reading files/running commands?
3. **Tone**: Was the agent helpful and concise following formatting rules? Did it avoid narrating its steps ("I will now check...")?
4. **Hallucination**: Identify any instances where the agent made up code, paths, command outputs, or fabricated tool results out of thin air.

For each category, provide:
- A rating: EXCELLENT / GOOD / NEEDS IMPROVEMENT / POOR
- Specific examples from the transcript supporting your rating
- Concrete recommendations for improvement

Finally, provide:
- An overall session quality rating
- Up to 3 specific recommendations for changes to the system prompt or ReAct logic.

Format your response as structured sections with clear headings.

## Session Transcript

{session_content}
"""


def review_chat(
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output raw AI response as JSON for CI integration."
    ),
):
    """
    Review the most recent agent console chat session with AI-powered UX analysis.

    Fetches the last chat session via fetch_last_chat_session.py, sends
    it to AI for analysis across accuracy, tool usage, tone, and
    hallucination categories, and outputs structured UX feedback.
    """
    # Locate the fetch script
    script_path = config.repo_root / ".agent" / "scripts" / "fetch_last_chat_session.py"
    if not script_path.exists():
        console.print(
            "[bold red]❌ fetch_last_chat_session.py not found at "
            f"{script_path}[/bold red]"
        )
        console.print(
            "[dim]Ensure .agent/scripts/fetch_last_chat_session.py exists.[/dim]"
        )
        raise typer.Exit(code=1)

    # Fetch the session
    console.print("[bold blue]💬 Fetching last chat session...[/bold blue]")
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
        console.print("[yellow]No active chat session found in console.db.[/yellow]")
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
        "chat_session_fetched",
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
    console.print("[bold blue]🤖 Analyzing chat session...[/bold blue]")
    analysis_start = time.time()

    from agent.core.ai import ai_service

    prompt = REVIEW_PROMPT.format(session_content=scrubbed_content[:50000])

    try:
        analysis = ai_service.complete(system_prompt="You are a UX Analyst.", user_prompt=prompt)
    except Exception as e:
        console.print(
            f"[bold red]❌ AI analysis failed: {e}[/bold red]"
        )
        logger.warning(
            "chat_analysis_failed",
            extra={"error": str(e)},
        )
        raise typer.Exit(code=1)

    analysis_duration = time.time() - analysis_start
    logger.info(
        "chat_analysis_complete",
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
                title="💬 Console Chat Session Review",
                border_style="blue",
            )
        )
        console.print()
        console.print(
            f"[dim]Analysis completed in {analysis_duration:.1f}s "
            f"(total: {total_duration:.1f}s)[/dim]"
        )
