---
description: Create a new implementation plan (Runbook) for a committed Story.
---

# Workflow: Create Implementation Runbook

1. **Run**: `agent new-runbook <STORY-ID>`
   - This invokes the CLI's internal AI Governance Panel, which automatically reads context, adopts panel roles, and generates a fully populated runbook for the given story.

2. **Review the Runbook**:
   - The generated runbook will be saved to `.agent/cache/runbooks/<SCOPE>/<STORY-ID>-runbook.md`.
   - Review the "Panel Review Findings", "Implementation Steps", and "Verification Plan".
   - Make any necessary manual adjustments or refinements.

3. **Mandatory Format Check — BEFORE accepting:**
   Implementation steps **MUST** be machine-executable, not prose. Reject any runbook where steps contain vague instructions like "move the logic" or "update this function". Every step must use one of these formats:

   **Modifying an existing file:**

   ```
   #### [MODIFY] .agent/src/path/to/file.py
   <<<SEARCH
   <exact verbatim lines from the current file>
   ===
   <exact replacement lines>
   >>>
   ```

   **Creating a new file:**

   ```
   #### [NEW] .agent/src/path/to/new_file.py
   ```python
   <complete file content — no placeholders>
   ```

   ```

   **Deleting a file:**
   ```

   #### [DELETE] .agent/src/path/to/old_file.py

   ```

   Key rules enforced here (not in the CLI):
   - Paths must be full repo-relative paths (no bare `src/` that could match node_modules).
   - SEARCH blocks must be verbatim — copied from the Codebase Introspection section.
   - No `<placeholder>` values anywhere in NEW file blocks.
   - One logical concern per `### Step N`.

4. **Status**:
   - Once reviewed and finalized, change `## State\nPROPOSED` to `## State\nACCEPTED` if you (acting as the Architect) are satisfied.
