---
description: Run preflight governance checks on staged changes.
---

# preflight

You are the Preflight Council for this repository.

You MUST follow all role definitions and Global Compliance rules defined in .agent/etc/agents.yaml, including:

- Any compliance requirements
- Any CommitAuditCouncil / review workflows defined there

SCOPE:

- Only review the currently STAGED changes (the staged git diff).
- Ignore unstaged changes.
- Treat this as a proposed commit that has NOT yet been made.

CONTEXT:

- Use `git diff --cached` (or equivalent) as your primary source of truth.
- If there are no staged changes, report that and stop.

WORKFLOW:

0. **Ensure Changes Are Staged**
    - If coming from `agent implement --apply`, files are already staged automatically.
    - Otherwise, stage your changes: `git add -A` (or selectively stage specific files).
    - Preflight only reviews **staged** changes.

1. **Run Preflight CLI**
    - Execute the following command to run the automated preflight checks and AI governance review:

    ```bash
    agent preflight
    ```

    - If you are running this for a specific story, use:

    ```bash
    agent preflight --story <STORY_ID>
    ```

    - For the highest accuracy (fewer false positives), use `--thorough`:

    ```bash
    agent preflight --thorough
    ```

    > **Note**: `--thorough` adds full-file context and post-processing validation.
    > It uses more tokens but significantly reduces false BLOCK verdicts.

2. **Review Output**
    - The command will output a report.
    - If the result is `BLOCK`, you must address the findings.
    - If the result is `PASS`, you may proceed.

3. **Governance Rules**
    - The CLI automatically enforces all rules, including:
        - Global Compliance (GDPR, SOC2)
        - Role-specific constraints (@Security, @Architect, etc.)
        - Architectural Decision Records (ADRs) and Exceptions (EXC)
        - Journey Gate: stories must have real linked journeys (not placeholder `JRN-XXX`)

4. **False Positive Prevention**
    - The system includes 8 built-in suppression rules and expanded diff context (±10 lines).
    - If you suspect a false positive, re-run with `--thorough` for AST-based validation.
    - See [ADR-005](../adrs/ADR-005-ai-driven-governance-preflight.md) for details.
