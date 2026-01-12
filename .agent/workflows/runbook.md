# Workflow: Create Implementation Runbook

1. **Run**: `agent new-runbook <STORY-ID>`
   - This attempts to generate a runbook using the CLI's internal AI Governance Panel.

2. **Populate the Runbook**:
   - You (the Agent) must now populate the content of the generated runbook.
   - **CRITICAL**: You must REFER TO (read) the following sources to ensure compliance and correctness. Do not hallucinate rules.
     - `Context: .agent/rules/` (Global Governance Rules)
     - `Context: .agent/etc/agents.yaml` (Role Definitions)
     - `Context: .agent/instructions/` (Detailed Role Instructions)
   - Adopt each role in the panel and fill out the "Panel Review Findings".
   - Create a detailed "Implementation Steps" plan.
   - Define a "Verification Plan".

3. **Status**:
   - Once populated, change `Status: PROPOSED` to `Status: ACCEPTED` if you (acting as the Architect) are satisfied.
