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
Token calculation utility and session usage tracker.
"""

import logging
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from agent.utils.sanitizer import scrub_text  # Created in Step 3

try:
    from observability.telemetry import record_token_usage as _record_token_usage
except ImportError:  # pragma: no cover
    _record_token_usage = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class UsageTracker:
    """
    Accumulates and reports token usage across multiple parallel tasks.
    Satisfies Acceptance Criteria for Scenario 2 (Cost Transparency).
    """

    def __init__(self) -> None:
        self.total_input = 0
        self.total_output = 0
        self.model_breakdown: Dict[str, Dict[str, int]] = {}
        self.console = Console()

    def record_call(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Add usage from a single LLM request and export to OTel backend."""
        self.total_input += input_tokens
        self.total_output += output_tokens

        if model not in self.model_breakdown:
            self.model_breakdown[model] = {"input": 0, "output": 0}

        self.model_breakdown[model]["input"] += input_tokens
        self.model_breakdown[model]["output"] += output_tokens

        # Export to OpenTelemetry metrics backend (no-op when OTel is unavailable)
        if _record_token_usage is not None:
            _record_token_usage(model, input_tokens, output_tokens)

    def print_summary(self) -> None:
        """Display a formatted summary table to the console."""
        if not self.model_breakdown:
            self.console.print("[yellow]No token usage recorded during this session.[/yellow]")
            return

        table = Table(title="LLM Token Consumption Summary", title_style="bold magenta")
        table.add_column("Model", style="cyan", no_wrap=True)
        table.add_column("Input Tokens", justify="right")
        table.add_column("Output Tokens", justify="right")
        table.add_column("Total Tokens", justify="right", style="bold green")

        for model, counts in self.model_breakdown.items():
            total = counts["input"] + counts["output"]
            table.add_row(
                model,
                f"{counts['input']:,}",
                f"{counts['output']:,}",
                f"{total:,}",
            )

        table.add_section()
        grand_total = self.total_input + self.total_output
        table.add_row(
            "TOTAL",
            f"{self.total_input:,}",
            f"{self.total_output:,}",
            f"{grand_total:,}",
            style="bold underline",
        )

        self.console.print("\n")
        self.console.print(table)
        self.console.print("[dim]Note: Metrics have been exported to the observability backend.[/dim]\n")


def get_token_count(text: str, model: str = "gpt-4") -> int:
    """
    Calculate the number of tokens in a string.
    Defaults to tiktoken for precise OpenAI counts, with a heuristic fallback.
    """
    if not text:
        return 0

    # Always ensure text is sanitized of PII before potential external counting/logging
    clean_text = scrub_text(text)

    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except (KeyError, ValueError):
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(clean_text, disallowed_special=()))
    except ImportError:
        # Fallback heuristic: roughly 4 characters per token if tiktoken is missing
        return len(clean_text) // 4
