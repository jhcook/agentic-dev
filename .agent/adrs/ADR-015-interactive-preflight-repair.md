# ADR-015: Interactive Preflight Repair

## Status

ACCEPTED

## Context

Developers frequently encounter preflight failures (linting, schema validation, tests) that block their workflows. Manually diagnosing and fixing these repetitive issues is inefficient. We need a way to automate these fixes while maintaining safety and governance standards.

## Decision

We will implement an `InteractiveFixer` module within the `agent` core that:

1. **Analyzes** preflight failures (initially Story Schema violations).
2. **Generates** fix proposals using the AI Service.
3. **Presents** options to the user via an interactive CLI.
4. **Applies** the chosen fix safely using `git stash` for rollback.
5. **Verifies** the fix by re-running the check.

We adopt **Ruff** as the primary linter to ensure high-performance analysis, minimizing latency during the interactive repair loop.

## Consequences

### Positive

- Reduced context switching for developers.
- Faster resolution of governance blockers.
- "Human-in-the-loop" maintains control.

### Negative

- risk of AI generating incorrect or insecure code (Mitigated by Security Validation and Diff Review).
- Increased complexity in the `agent` CLI.

## Security & Safety

- **AI Validation**: All AI-generated code is validated against a blacklist of dangerous patterns (e.g., `import os`, `subprocess`, `exec`) and parsed via AST to detect malicious calls before being presented to the user.
- **Sandboxing**: Fixes are applied in the local environment but require explicit user confirmation after a Diff preview. Future iterations will explore containerized sandboxing.
- **Rollback**: The system uses `git stash push` before applying any fix. On failure or user rejection, `git stash pop` restores the original state.
- **Secrets**: API keys and secrets are scrubbed from all logs and outputs.

## Compliance (GDPR & SOC2)

- **Data Minimization**: Only the specific file content relevant to the failure is sent to the AI.
- **PII Scrubbing**: All AI prompts and responses are scrubbed for PII using the `scrub_sensitive_data` utility.
- **Lawful Basis**: Processing is necessary for the performance of the developer contract (tooling support).
- **Retention**: AI prompts are ephemeral and not stored by the Agent beyond the request duration. Logs are strictly local.
- **Legal Review**: The use of `.auditignore` and AI integration has been reviewed for compliance risks.
- **Audit Trail**: All fix operations are logged locally (without PII) to support security audits.
