---
description: 
---

# pr

You are opening a Pull Request for the current branch.

STEP 1 — PREFLIGHT:
- Check if currently on a story branch or if a story ID can be inferred.
- Run `agent preflight --story STORY-ID`.
- If preflight fails, ABORT.

STEP 2 — PULL REQUEST:
- Use `gh pr create --draft --web`.
- Auto-fill title with "[STORY-ID] <Title from Commit/Prompt>".
- Auto-fill body with template:
  - Story Link: (link to story file or issue)
  - Changes: (summary of changes)
  - Governance Checks: ✅ Preflight Passed

STEP 3 — EXECUTION:
- Execute `gh pr create --draft` with the generated arguments.
- Allow user to edit the PR description if possible (or pass `--web` if preferred).