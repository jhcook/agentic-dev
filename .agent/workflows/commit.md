# Workflow: Commit Changes

1. **Context Check**:
   - Infer the Story ID (e.g., from branch name or active task).
   - Review the staged changes (`git diff --staged`).

2. **Generate Message**:
   - You (the Agent) must generate a **Conventional Commit** message.
   - Format: `<type>(<scope>): <subject>`
   - Rules:
     - Use present tense.
     - Max 72 chars for subject.
     - Type must be one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.

3. **Execute**:
   - **Run**: `agent commit -m "<MESSAGE>"` \
     *(Note: This command will automatically prepend the Story ID)*
   
   - *Example*: `agent commit -m "fix(cli): resolve unbound variable error in shim"`
