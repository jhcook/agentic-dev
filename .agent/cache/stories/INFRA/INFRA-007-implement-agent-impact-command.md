# INFRA-007: Implement Agent Impact Command

## State
COMMITTED

## Problem Statement
The "Impact Analysis Summary" section in stories is critical for governance but often difficult to populate accurately manually. Developers may miss subtle dependencies or downstream effects of their changes. Automated analysis is needed to ensure this section is meaningful and accurate.

## User Story
As a Developer, I want to run `agent impact <story-id>` so that I can get an AI-generated analysis of how my changes affect the rest of the system, identifying potential risks, breaking changes, and affected workflows.

## Acceptance Criteria
- [ ] **Scenario 1**: Can run `agent impact <story-id>` with staged changes and receive a text analysis of the impact.
- [ ] **Scenario 2**: Can run `agent impact <story-id> --base main` to compare against a specific branch.
- [ ] **Scenario 3**: Can run with `--update-story` flag to automatically populate the "Impact Analysis Summary" section of the story markdown file.
- [ ] **Scenario 4**: The analysis correctly identifies basic risks (e.g., modifying a shared utility, changing a public CLI signature).
- [ ] **Scenario 5**: Fails gracefully if no changes are detected.

## Non-Functional Requirements
- **Performance**: Analysis should complete within reasonable time (AI latency driven).
- **Security**: Diff must be scrubbed of PII/Secrets before sending to AI (via `scrub_sensitive_data`).
- **Observability**: Logging of AI usage.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/check.py`, `agent/core/ai/prompts.py` (assumed new)
Workflows affected: Governance workflows.
Risks identified: Low risk, purely additive command.

## Test Strategy
- Unit tests for the `impact` command logic.
- Mock the AI service to verify prompt construction and response handling.
- Integration test ensuring the file update mechanism works.

## Rollback Plan
- Revert the changes to `agent/commands/check.py`.
