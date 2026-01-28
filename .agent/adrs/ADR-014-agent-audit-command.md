# ADR-007: Agent Audit Command

## Status
Accepted

## Context
The project requires a mechanism to enforce "Governance as Code", ensuring:
-   Traceability of code to requirements (Stories/Runbooks).
-   Identification of stagnant or orphaned code/artifacts.
-   Compliance with licensing and security standards.

Previously, these checks were manual or ad-hoc. We need a centralized CLI command to perform these audits.

## Decision
We will implement an `agent audit` command.

### Architecture
-   **Layering**:
    -   `agent/commands/audit.py`: CLI Entry point (Typer). Handles flags and output formatting.
    -   `agent/core/governance.py`: Core logic. Contains `AuditResult` dataclass and scanning algorithms (`find_stagnant_files`, `check_license_headers`).
    -   `agent/core/security.py`: used for PII scrubbing of report output.

### Logic
1.  **Traceability**: Files checking for key headers (STORY-XXX).
2.  **Stagnancy**: Git log analysis for file age.
3.  **Licensing**: Header verification (Apache 2.0).
4.  **Reporting**: Markdown output with PII scrubbing.

### Scalability
-   Iterative file scanning (generators) to handle large repos.
-   `.auditignore` support to skip irrelevant trees (`node_modules`).

## Consequences
### Positive
-   Automated compliance verification.
-   SOC2 evidence generation (audit logs).

### Negative
-   Scan time performance impact on large repositories (mitigated by ignores).
