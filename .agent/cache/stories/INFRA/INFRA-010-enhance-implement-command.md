# INFRA-010: Enhance Implement Command

## Parent Plan
INFRA-008

## State
OPEN

## Problem Statement
The `agent implement` command currently only generates advice as Markdown. It does not help the developer by actually applying the changes, which reduces the "agentic" value.

## User Story
As a developer, I want to run `agent implement <RUNBOOK_ID> --apply` so that the agent automatically modifies the files as per the runbook.

## Acceptance Criteria
- [ ] `agent implement` accepts an `--apply` flag.
- [ ] When `--apply` is used, the agent parses code blocks from the AI response.
- [ ] The agent applies the changes to the file system.
- [ ] The agent prompts for confirmation before writing files (unless `--yes` is passed).

## Impact Analysis Summary
Components touched: `agent/commands/implement.py`
Workflows affected: Implementation.
Risks identified: AI generating bad code or overwriting files incorrectly.

## Test Strategy
- Create a dummy runbook.
- Run `agent implement --apply`.
- Verify file changes are applied correctly.
