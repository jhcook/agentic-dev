# ADR-018: Node Tooling Strategy

## Status

Accepted

## Context

The Agentic Development environment is primarily Python-based. However, the ecosystem for certain tools (specifically linting and web frontend) is dominated by Node.js.
We recently introduced `markdownlint` to improve documentation quality. This tool is distributed via `npm`.

We need a consistent strategy for handling Node.js-based tools within our Python-centric CLI to ensure:

1. **Reproducibility**: Tools should behave consistently across environments.
2. **Ease of Use**: Users shouldn't need to manually manage complex `npm` globals if possible.
3. **Resilience**: The Python agent should not crash if Node.js is missing (unless working on web components).

## Decision

We will adopt a "Graceful Hybrid" strategy for Node.js tooling:

1. **Prefer `npx`**: When running Node-based CLIs (like `eslint`, `markdownlint`), the Python Agent (`lint.py`) will prioritize invoking them via `npx --no-install` (or `npx --yes` for temporary execution). This ensures we use project-local versions defined in `package.json` if present, or ephemeral latest versions if ephemeral usage is intended and safe.
2. **Global Fallback**: If `npx` is not available or slow, we check for a globally installed binary (e.g., `markdownlint`).
3. **Graceful Degradation**: If neither `npx` nor the binary is found:
    - For **Core Critical** tasks (like Web builds), we fail and prompt the user.
    - For **Auxiliary** tasks (like Linting text files), we log a warning (`[dim]Skipping...[/dim]`) and **proceed without failure**. This prevents blocking Python developers who may not have Node installed from running basic Python workflows.
4. **Onboarding**: The `agent onboard` command will check for `node`, `npm`, and recommended tools, offering to install them if missing, but will not mandate them for core operation.

## Consequences

- **Positive**:
  - Python devs don't need Node for basic work.
  - CI/CD can bring its own Node environment.
  - Linting is "best effort" locally but strict in CI (where Node is present).
- **Negative**:
  - Linting results might vary if a user doesn't have the tool installed (false positives/negatives vs CI).
  - First run of `npx` might be slow.

## Compliance

- **Security**: `npx` usage must be scrutinized. We pin versions in `package.json` where possible.
- **Privacy**: No additional PII risk.
