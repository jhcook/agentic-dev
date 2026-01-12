---
trigger: always_on
description: Enforce strict state transitions for Plans, Stories, and Runbooks.
globs: ["**/*.md"]
---

# Governance State Enforcement

To ensure high-quality, governed development, the following state transitions are enforced:

## 1. Plans
- **File**: `.agent/cache/plans/<SCOPE>/<ID>.md`
- **Required State**: `Status: APPROVED`
- **Constraint**: A Story cannot be created or worked on until its parent Plan is APPROVED.

## 2. Stories
- **File**: `.agent/cache/stories/<SCOPE>/<ID>.md`
- **Required State**: `State: COMMITTED` (or `Status: COMMITTED`) `State: OPEN` (or `Status: OPEN`)
- **Constraint**: A Runbook cannot be created for a Story unless the Story is COMMITTED.
- **Meaning**: The requirements are finalized and "locked in".

## 3. Runbooks
- **File**: `.agent/cache/runbooks/<SCOPE>/<ID>-runbook.md`
- **Required State**: `Status: ACCEPTED`
- **Constraint**: The `agent implement` command will fail unless the Runbook is ACCEPTED.
- **Meaning**: The implementation plan and architectural approach have been reviewed and approved by the Governance Panel (or the Agent acting as proxy).