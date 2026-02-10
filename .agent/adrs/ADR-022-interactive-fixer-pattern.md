# ADR-022: Interactive Fixer Pattern

## Status

ACCEPTED

## Context

The original governance validation flow was strict and binary: a story was either VALID or INVALID. If invalid, the process failed, and the developer had to manually fix the markdown file. This approach:

1. Slowed down development velocity.
2. Did not leverage the Agent's capabilities to self-correct.
3. Provided a poor experience for Voice Agent users who cannot easily "open an editor".

## Decision

We are adopting an **Interactive Fixer Pattern** for governance checks (Stories, Runbooks).

### Key Components

1. **Strict Validation, Soft Failure**: The system still strictly validates schemas (using `agent validate-story`).
2. **Analysis Phase**: If validation fails, `InteractiveFixer` uses AI to analyze the missing sections and generate structured JSON fix options.
3. **Approbation Phase**: The user (via CLI or Voice) is presented with these options and chooses one.
4. **Verification Loop**: The selected fix is applied, and validation is run *again*. If validation fails (regression or bad fix), changes are automatically reverted.
5. **Stateful Tooling**: The `interactive_fix_story` tool manages this state (Analyze -> Apply) to support both single-turn CLI usage and multi-turn Voice usage.

## Consequences

### Positive

- **Velocity**: Fixes are generated and applied in seconds.
- **Accessibility**: Voice Agent users can "fix" governance issues verbally.
- **Robustness**: The Verification Loop ensures AI-generated fixes are valid before committing them.

### Negative

- **Complexity**: Introduces state management in tools and dependency on AI availability.
- **Security**: AI generating code/text requires sanitization (addressed via `scrub_sensitive_data` and subprocess isolation).

## Compliance

This pattern complies with governance by ensuring that *human approval* (selection of the option) is required before any AI-generated content is persisted as truth.
