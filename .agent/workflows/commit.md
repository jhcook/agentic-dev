---
description: Commit changes using the agent with a conventional commit message.
---

# Workflow: Commit Changes

1. **Resolve Story ID**
- Check if the user provided, e.g., /commit INFRA-088
- Check the current branch name: `git branch --show-current`
- If the branch name contains a story ID pattern (e.g., `INFRA-088-some-feature`), extract it.
- If the branch is `main`, `master`, `develop`, or does NOT contain a story ID:
  - Run `agent match-story` to auto-detect the story ID from staged changes.
  - If `match-story` returns a story ID, use it with `--story <STORY_ID>`.
  - If `match-story` cannot find a story ID, **notify the user** with:
        `"Cannot determine Story ID. Please specify with: agent commit --story <STORY_ID>"`
        and **stop** — do NOT run commit without a story ID.

1. **Get Context**
   - Review the staged changes (`git diff --staged`).

2. **Execute**:
   - **Run**: `agent commit --story <STORY_ID> -y`
   - *(Always use the `-y` flag when executing this via an agent to prevent interactive text editors from hanging the session).*
   - The CLI will automatically infer the Story ID, prepend it, and use AI to generate a Conventional Commit message based on the staged changes.

3. **Manual Override (Optional)**:
   - If you want to bypass the AI and provide your own message, use the `-m` flag.
   - **Run**: `agent commit -m "<MESSAGE>" -y`
   - *Example*: `agent commit -m "fix(cli): resolve unbound variable error in shim" -y`
   - The CLI will still automatically prepend the Story ID to your message.

## Copyright

Copyright 2026 Justin Cook
