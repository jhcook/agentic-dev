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

import typer
from pathlib import Path
from typing import Optional
import logging
import json
from datetime import datetime

from agent.core.governance import run_audit, log_governance_event
from agent.core.formatters import format_audit_report
from agent.core.security import scrub_sensitive_data

app = typer.Typer()
logger = logging.getLogger(__name__)

@app.command()
def audit(
    repo_path: Path = typer.Option(
        Path("."), help="Path to the repository to audit."
    ),
    min_traceability: int = typer.Option(
        80, help="Minimum percentage of files that must be traceable to a story or runbook."
    ),
    stagnant_months: int = typer.Option(
        6, help="Number of months after which a file is considered stagnant."
    ),
    output: Optional[Path] = typer.Option(
        None, help="Path to save the audit report. Defaults to AUDIT-<Date>.md in the current directory."
    ),
    fail_on_error: bool = typer.Option(
        False, help="Exit with a non-zero code if any issues are found."
    ),
    json_output: bool = typer.Option(
        False, help="Output the report in JSON format instead of Markdown."
    ),
    all_files: bool = typer.Option(
        False, "--all", "-a", help="Scan all files, ignoring .gitignore and .auditignore (except .git/)."
    ),
):
    """
    Run a governance audit of the repository.
    """
    try:
        ignore_patterns = []
        
        # Always ignore .git/ directory
        ignore_patterns.append(".git/")

        if not all_files:
            # Load .gitignore patterns
            gitignore_path = repo_path / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path, "r") as f:
                    gitignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    ignore_patterns.extend(gitignore_patterns)

            # Load .auditignore patterns
            auditignore_path = repo_path / ".auditignore"
            if auditignore_path.exists():
                with open(auditignore_path, "r") as f:
                    auditignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    ignore_patterns.extend(auditignore_patterns)

        # Run the audit
        log_governance_event("AUDIT_RUN", f"Running audit on {repo_path} with options: min_traceability={min_traceability}, stagnant_months={stagnant_months}, all_files={all_files}")
        result = run_audit(
            repo_path=repo_path,
            min_traceability=min_traceability,
            stagnant_months=stagnant_months,
            ignore_patterns=ignore_patterns,
        )

        # Determine output path
        if output is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            output_path = repo_path / f"AUDIT-{date_str}.md"
        else:
            output_path = output

        # Generate and save the report
        if json_output:
            report_content = json.dumps(result.__dict__, indent=4)
            output_path = output_path.with_suffix(".json")
        else:
            report_content = format_audit_report(result)

        # Scrub output before saving
        report_content = scrub_sensitive_data(report_content)

        with open(output_path, "w") as f:
            f.write(report_content)

        print(f"Audit report saved to {output_path}")

        # Exit with appropriate code based on findings
        if fail_on_error:
            if result.traceability_score < min_traceability or result.ungoverned_files or result.stagnant_files or result.orphaned_artifacts or result.errors:
                raise typer.Exit(code=1)

    except Exception as e:
        logger.error(f"An error occurred during the audit: {e}", exc_info=True)
        print(f"An error occurred during the audit: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()