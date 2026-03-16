---
description: Implement a feature from an accepted Runbook using AI automation.
---

# Workflow: Implement

Run the following command to have the AI implement the runbook automatically:
`agent implement <RUNBOOK-ID> --apply`

> **Note:** `--apply` writes files to disk but does **not** commit. Add `--commit` to auto-commit each step.

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
# Apply files to disk only (no staging, no commit)
agent implement <RUNBOOK-ID> --apply

# Apply and stage modified files for commit (recommended)
agent implement <RUNBOOK-ID> --apply --stage

# Apply, stage, AND auto-commit each step (legacy behavior)
agent implement <RUNBOOK-ID> --apply --commit
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
3. Run `agent implement <RUNBOOK-ID> --apply --stage --yes` (add `--commit` instead of `--stage` if you want auto-commits per step).

The python CLI orchestrator will:
- Check for required linked journeys.
- Segment the runbook into manageable implementation tasks.
- Generate the code, apply the diffs, and create backups.
- Automatically execute the `@Security` and `@QA` governance gates (**non-fatal warnings**).
- Stage the modified files and update the Notion sync state.

## GOVERNANCE LIFECYCLE

`agent implement` and `agent preflight` have distinct, complementary roles:

| Command | Role | Gate mode |
|---------|------|-----------|
| `agent implement` | **Land the code** — apply runbook steps to disk | Gates are **warnings** (yellow ⚠️) — never block |
| `agent preflight` | **Certify readiness** — verify the branch before a PR | Gates are **hard blocks** (red ❌) — PR is gated |

This separation means `implement` focuses on landing code, while `preflight` is the enforcement point.

**Recommended workflow** (`--stage`):
```
agent implement INFRA-103 --apply --stage --yes
  ├── ⚡ Apply all runbook steps to disk ✅
  ├── 📦 Stage modified files (git add) ✅
  ├── 🔒 Post-Apply Governance Gates (warnings only)
  └── Files staged, ready for preflight

agent preflight --story INFRA-103
  └── ← hard BLOCK here if gates fail ✅

agent commit -y
  └── Governed commit with AI-generated message ✅

agent pr
  └── Push + open PR ✅
```

**With auto-commit** (`--commit`):
```
agent implement INFRA-103 --apply --commit --yes
  ├── ⚡ Apply all runbook steps (micro-committed per step) ✅
  ├── 🔒 Post-Apply Governance Gates (warnings only)
  └── Code already committed — run preflight next
```

If `implement` finishes with story state `REVIEW_NEEDED`, always run `agent preflight --story <ID>` (with `--thorough` for fewest false positives) before opening a PR.

## FALLBACK: MANUAL IMPLEMENTATION

If the CLI command fails (e.g., due to AI context length limits or complex refactoring that requires deep multi-file reasoning), you must fall back to manual implementation:

1. Read the Runbook.
2. Architect the solution in your context.
3. Write the code using file editing tools.
4. Manually run `make test`.
5. Run `agent preflight --story <STORY-ID>` to validate your manual changes against the Governance Council.

## Copyright

Copyright 2026 Justin Cook
