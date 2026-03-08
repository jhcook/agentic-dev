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

from rich.console import Console

def print_reference_summary(console: Console, roles_data: list, ref_metrics: dict, finding_validation: dict | None = None) -> None:
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

