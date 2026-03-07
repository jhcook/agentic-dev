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
   Implementation steps **MUST** be machine-executable. Reject any runbook step written as
   prose (e.g. "move this logic" or "update this function"). Every step must use one of:

   - `#### [MODIFY] <full/repo/relative/path>` — followed by `<<<SEARCH/===/>>>` blocks
     containing verbatim lines from the current file.
   - `#### [NEW] <full/repo/relative/path>` — followed by complete file content in a
     fenced code block. No placeholders.
   - `#### [DELETE] <full/repo/relative/path>` — followed by a one-line rationale comment.

   Key rules:
   - Paths are full repo-relative paths from the repo root (no ambiguous bare directory names).
   - SEARCH text is copied verbatim from the Codebase Introspection section — not invented.
   - One logical concern per `### Step N` — split steps if needed.

4. **Status**:
   - Once reviewed and finalized, change `## State\nPROPOSED` to `## State\nACCEPTED` if you (acting as the Architect) are satisfied.
