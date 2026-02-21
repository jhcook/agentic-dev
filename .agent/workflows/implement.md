---
description: Implement a feature from an accepted Runbook using AI automation.
---

# Workflow: Implement

Run the following command to have the AI implement the runbook automatically:
`agent implement <RUNBOOK-ID> --apply`

---

# Implementation Guide

You (the AI Agent) are an implementation assistant for this repository.
The `agent implement` command now encapsulates the majority of the legacy workflow through autonomous agents.

## PURPOSE

Implement a feature, fix, or enhancement following strict quality gates managed by the CLI:

1. Journey enforcement (Automated)
2. AI-driven implementation (Automated)
3. Security scanning (Automated)
4. Quality assurance / Testing (Automated)

## SYNTAX

```bash
agent implement <RUNBOOK-ID> --apply
```

If you need to force a specific provider (like Gemini or Anthropic):
```bash
agent implement <RUNBOOK-ID> --apply --provider gemini
```

## YOUR ROLE AS THE AGENT

When the user requests that you execute the `/implement` workflow, you should NOT manually write the code file-by-file. 

Instead, you must **delegate the work to the CLI orchestration**:
1. Check the git status to ensure the working directory is clean.
2. Ensure the correct story branch is checked out.
3. Run `agent implement <RUNBOOK-ID> --apply --yes`.

The python CLI orchestrator will:
- Check for required linked journeys.
- Segment the runbook into manageable implementation tasks.
- Generate the code, apply the diffs, and create backups.
- Automatically execute the `@Security` and `@QA` governance gates.
- Stage the modified files and update the Notion sync state.

## FALLBACK: MANUAL IMPLEMENTATION

If the CLI command fails (e.g., due to AI context length limits or complex refactoring that requires deep multi-file reasoning), you must fall back to manual implementation:

1. Read the Runbook.
2. Architect the solution in your context.
3. Write the code using file editing tools.
4. Manually run `make test`.
5. Run `agent preflight --story <STORY-ID>` to validate your manual changes against the Governance Council.
