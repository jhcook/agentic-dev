# ADR-016: OpenAI as Third-Party Data Processor

Date: 2026-01-11

## Status

Proposed

## Context

The Agent CLI moves to a Python implementation that leverages AI for advanced governance workflows, specifically:
- `agent plan`: Generates implementation plans from stories.
- `agent implement`: Generates code/files from plans.
- `agent match-story`: Matches code branches to stories.
- `agent new-runbook`: Generates runbooks from tasks.

These commands require sending context to an LLM, including:
1.  **Governance Rules**: All files in `.agent/rules/`.
2.  **Internal Documentation**: User stories, existing runbooks, and implementation plans.
3.  **File Paths**: Lists of changed files.

This constitutes a transfer of internal (potentially proprietary) data to a third-party processor (OpenAI or Google Gemini).

## Decision

We will use **OpenAI (via API)** and **Google Gemini (via API)** as the backend providers for these AI features.

### Justification
The productivity gains from AI-assisted governance (checking rules against plans, generating boilerplates) significantly outweigh the risk of exposing non-PII internal documentation to enterprise-grade API providers.

### Data Privacy & Compliance
1.  **No Training**: We rely on the standard enterprise API terms of OpenAI/Google which state that API data is **not used for model training** by default.
2.  **Data Minimization**: We only send the text content necessary for the specific task (System Prompt + specific Story/Plan). We do not send the full codebase repository in bulk.
3.  **PII Policy**:
    - **User Responsibility**: Users are strictly prohibited from including PII (Personal Identifiable Information) or Secrets (API Keys, passwords) in Stories, Runbooks, or Plans.
    - **Enforcement**: The CLI will emit a warning before every AI request reminding the user of this policy.
    - **Sanitization**: Active regex-based sanitization is **implemented** on all Story and Diff content before transfer to the LLM (using `agent.core.utils.scrub_sensitive_data`). This automatically redacts Emails, IPs, API Keys, and Private Keys supplementary to the user adherence policy.

## Consequences

### Positive
- drastically reduced time to create compliance artifacts.
- higher consistency in following governance rules (as AI "reads" them all).

### Negative
- Dependence on external network/APIs for core workflow commands.
- Risk of accidental data leak if user ignores "No PII" policy.

## Compliance
This ADR serves as the formal record of Third-Party Data Processing for GDPR/SOC 2 purposes regarding the Agent CLI.

## Changes
- **2026-01-11**: Updated PII Policy to reflect implemented active regex-based sanitization (`scrub_sensitive_data`).
