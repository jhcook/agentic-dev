---
description: Create a Pull Request with preflight checks.
---

# pr

You are opening a Pull Request for the current branch.

STEP 1 — PREFLIGHT:
You are the Preflight Council for this repository.

You MUST follow all role definitions and Global Compliance rules defined in .agent/etc/agents.yaml, including:
- Any compliance requirements
- Any CommitAuditCouncil / review workflows defined there

SCOPE:
- Only review the current branch commits.
- Ignore unstaged changes.
- Treat this as a proposed merge that has NOT yet been made.

CONTEXT:
- Use `git diff main...HEAD` (or equivalent) as your primary source of truth.
- If there are no staged changes, report that and stop.

WORKFLOW:

1. LOAD RULES
   - Load and apply all rules from .agent/rules/ and .agent/instructions/<role>/ (all `*.md?` files).
   - Especially enforce:
     - Security, SOC 2, GDPR
     - Lint / code quality expectations
     - Documentation / auditability requirements
     - Architectural boundaries and data flows

2. ROLE REVIEWS
   Act as each role, staying strictly within their remit.

3. OVERALL OUTCOME
   - If ANY role returns BLOCK, the overall preflight verdict is BLOCK.
   - Only if ALL roles return APPROVE is the overall preflight verdict APPROVE.


STEP 2 — PULL REQUEST:
- Use `gh pr create --draft --web`.
- Auto-fill title with "[STORY-ID] <Title from Commit/Prompt>".
- Auto-fill body with template:
  - Story Link: (link to story file or issue)
  - Changes: (summary of changes)
  - Governance Checks: ✅ Preflight Passed

STEP 3 — EXECUTION:
- Execute `gh pr create --draft --web` with the generated arguments.

NOTES:
- Do NOT run git commit.
- Do NOT modify files.
- Focus only on analysis and actionable feedback.
- Keep findings concise and highly actionable.