---
description: Commit changes using the agent with a conventional commit message.
---

# Workflow: Commit Changes

1. **Context Check**:
   - Infer the Story ID (e.g., from branch name or active task).
   - Review the staged changes (`git diff --staged`).

2. **Execute**:
   - **Run**: `agent commit`
   - The CLI will automatically infer the Story ID, prepend it, and use AI to generate a Conventional Commit message based on the staged changes.

3. **Manual Override (Optional)**:
   - If you want to bypass the AI and provide your own message, use the `-m` flag.
   - **Run**: `agent commit -m "<MESSAGE>"`
   - *Example*: `agent commit -m "fix(cli): resolve unbound variable error in shim"`
   - The CLI will still automatically prepend the Story ID to your message.
