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

1. **Run Preflight CLI**
    - Execute the following command to run the automated preflight checks and AI governance review:

    ```bash
    agent preflight --ai
    ```

    - If you are running this for a specific story, use:

    ```bash
    agent preflight --ai --story <STORY_ID>
    ```

2. **Review Output**
    - The command will output a report.
    - If the result is `BLOCK`, you must address the findings.
    - If the result is `PASS`, you may proceed.

3. **Governance Rules**
    - The CLI automatically enforces all rules, including:
        - Global Compliance (GDPR, SOC2)
        - Role-specific constraints (@Security, @Architect, etc.)
        - Architectural Decision Records (ADRs) and Exceptions (EXC)
