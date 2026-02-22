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

3. **Status**:
   - Once reviewed and finalized, change `## State\nPROPOSED` to `## State\nACCEPTED` if you (acting as the Architect) are satisfied.
