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
    - If coming from `agent implement --apply --stage`, files are already staged. If using `--apply` alone, run `git add` before preflight. (`--commit` implies staging.)
    - Otherwise, stage your changes: `git add -A` (or selectively stage specific files).
    - Preflight only reviews **staged** changes.

1. **Resolve Story ID**
    - Check if the user provided, e.g., /preflight INFRA-088
    - Check the current branch name: `git branch --show-current`
    - If the branch name contains a story ID pattern (e.g., `INFRA-088-some-feature`), extract it.
    - If the branch is `main`, `master`, `develop`, or does NOT contain a story ID:
      - Run `agent match-story` to auto-detect the story ID from staged changes.
      - If `match-story` returns a story ID, use it with `--story <STORY_ID>`.
      - If `match-story` cannot find a story ID, **notify the user** with:
        `"Cannot determine Story ID. Please specify with: agent preflight --story <STORY_ID>"`
        and **stop** — do NOT run preflight without a story ID.

2. **Run Preflight CLI**
    - Execute the following command to run the automated preflight checks and AI governance review:

    ```bash
    agent preflight --story <STORY_ID>
    ```

    - For the highest accuracy (fewer false positives), use `--thorough`:

    ```bash
    agent preflight --story <STORY_ID> --thorough
    ```

    > **Note**: `--thorough` adds full-file context and post-processing validation.
    > It uses more tokens but significantly reduces false BLOCK verdicts.

3. **Review Output**
    - The command will output a report.
    - If the result is `BLOCK`, you must address the findings.
    - If the result is `PASS`, you may proceed.

4. **Governance Rules**
    - The CLI automatically enforces all rules, including:
        - Global Compliance (GDPR, SOC2)
        - Role-specific constraints (@Security, @Architect, etc.)
        - Architectural Decision Records (ADRs) and Exceptions (EXC)
        - Journey Gate: stories must have real linked journeys (not placeholder `JRN-XXX`)

5. **False Positive Prevention**
    - The system includes 8 built-in suppression rules and expanded diff context (±10 lines).
    - If you suspect a false positive, re-run with `--thorough` for AST-based validation.
    - See [ADR-005](../adrs/ADR-005-ai-driven-governance-preflight.md) for details.
