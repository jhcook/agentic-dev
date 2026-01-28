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

from agent.core.governance import AuditResult
from datetime import datetime

def format_audit_report(result: AuditResult) -> str:
    """Generate AUDIT-<Date>.md markdown report."""
    report = f"""# Governance Audit Report - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

This report provides an overview of the governance status of the repository. It assesses traceability, identifies stagnant code, and flags orphaned governance artifacts.

- **Overall Traceability Score:** {get_health_indicator(result.traceability_score)} {result.traceability_score:.2f}%
- **Ungoverned Files:** {len(result.ungoverned_files)}
- **Stagnant Files:** {len(result.stagnant_files)}
- **Orphaned Artifacts:** {len(result.orphaned_artifacts)}
- **Errors:** {len(result.errors)}

## Detailed Findings

### Traceability

- **Score:** {get_health_indicator(result.traceability_score)} {result.traceability_score:.2f}%

The traceability score indicates the percentage of files that are linked to a story or runbook. A lower score indicates a higher risk of ungoverned code.

#### Ungoverned Files (Top 10)

These files are not traceable to a story or runbook and should be reviewed.

"""
    if result.ungoverned_files:
        report += "| File | \n| --- | \n"
        for file in result.ungoverned_files[:10]:
            report += f"| {file} |\n"
    else:
        report += "No ungoverned files found.\n"

    report += """
### Stagnant Code

These files have not been modified in a while and may represent dead code or technical debt.

"""
    if result.stagnant_files:
        report += "| File | Last Modified | Days Old |\n|---|---|---|\n"
        for file in result.stagnant_files[:10]:
            report += f"| {file['path']} | {file['last_modified']} | {file['days_old']} |\n"
    else:
        report += "No stagnant files found.\n"

    report += """
### Orphaned Artifacts

These stories or plans are in an open state but have not been updated recently.

"""
    if result.orphaned_artifacts:
        report += "| Artifact | State | Last Activity | Days Old |\n|---|---|---|---|\n"
        for artifact in result.orphaned_artifacts[:10]:
            report += f"| {artifact['path']} | {artifact['state']} | {artifact['last_activity']} | {artifact['days_old']} |\n"
    else:
        report += "No orphaned artifacts found.\n"
        
    report += """
### Errors

The following errors were encountered during the audit.

"""
    if result.errors:
        report += "| Error |\n|---|\n"
        for error in result.errors:
            report += f"| {error} |\n"
    else:
        report += "No errors found.\n"

    return report


def get_health_indicator(score: float) -> str:
    """Return a health indicator based on the score."""
    if score >= 80:
        return "✅"
    elif score >= 50:
        return "⚠️"
    else:
        return "❌"


def format_data(format_type: str, data: list[dict[str, any]]) -> str:
    """
    Format a list of dictionaries into the specified string format.
    
    Args:
        format_type: One of 'json', 'csv', 'yaml', 'markdown', 'plain', 'tsv'.
        data: List of dictionaries to format.
        
    Returns:
        Formatted string.
        
    Raises:
        ValueError: If format is unknown or data serialization fails.
    """
    if not data:
        return ""

    if format_type.lower() == "json":
        import json
        return json.dumps(data, indent=2, default=str)

    elif format_type.lower() == "yaml":
        import yaml
        return yaml.dump(data, sort_keys=False, default_flow_style=False)

    elif format_type.lower() in ["csv", "tsv"]:
        import csv
        import io
        
        output = io.StringIO()
        if not data:
            return ""
            
        keys = data[0].keys()
        delimiter = "\t" if format_type.lower() == "tsv" else ","
        writer = csv.DictWriter(output, fieldnames=keys, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    elif format_type.lower() == "markdown":
        if not data:
            return ""
        
        keys = list(data[0].keys())
        # Header
        md = "| " + " | ".join(keys) + " |\n"
        md += "| " + " | ".join(["---"] * len(keys)) + " |\n"
        
        # Rows
        for row in data:
            values = [str(row.get(k, "")) for k in keys]
            md += "| " + " | ".join(values) + " |\n"
        return md

    elif format_type.lower() == "plain":
        # Simple key=value format
        lines = []
        for row in data:
            lines.append(" ".join(f"{k}={v}" for k, v in row.items()))
        return "\n".join(lines)
        
    elif format_type.lower() == "pretty":
        # Usually handled by Rich in the caller, but if called here, return JSON as fallback
        import json
        return json.dumps(data, indent=2, default=str)

    else:
        raise ValueError(f"Unknown format: {format_type}")