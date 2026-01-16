# INFRA-018: Implement Agent Retrospective

## State
COMMITTED

## Problem Statement
We are accumulating completed stories and runbooks, but we lack a systematic way to learn from them. There is no automated feedback loop to identify which stories caused the most friction (e.g., high churn, failed checks) or to compare the planned work against the actual execution. This leads to repeated mistakes and stagnant velocity.

## User Story
As a Product Owner or Team Lead, I want to run `agent retrospective` to generate a report on recently completed stories, identifying process bottlenecks and quality issues, so that we can improve our workflows and estimations.

## Acceptance Criteria
- [ ] **Data Gathering**: The command scans the `.agent/cache` for stories with state `CLOSED` or `COMPLETED`. Defaults to looking back 14 days, configurable via `--days`.
- [ ] **Metric Extraction**: For each story, it extracts:
    - Cycle time (based on file creation/mod time).
    - "Churn" (number of commits/edits linked to the story).
    - Compliance failures (recorded in preflight logs).
- [ ] **AI Analysis**: The collected data is summarized by the LLM to highlight "Friction Assessment" (Start/Stop/Continue).
- [ ] **Comparator**: Attempts to compare "Plan" text vs "Actual" (git diff). **CRITICAL**: The git diff must be PII scrubbed *before* being sent to the AI.
- [ ] **Report Output**: Generates a `RETROSPECTIVE-<Date>.md` human-readable report AND a `retrospective.json` machine-readable file in `.agent/reports/`.
- [ ] **Persistence**: The `.agent/reports/` directory should be added to `.gitignore` to prevent repository bloat (developers can manually commit if desired).

## Non-Functional Requirements
- **Privacy**: Strict PII scrubbing on all logs and diffs sent to the LLM.
- **Determinism**: The metrics calculation must be deterministic; only the qualitative summary is generative.
- **Speed**: Report generation should complete within 30 seconds for the default time window.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/retrospective.py` (new), `agent/core/analytics.py` (new).
Workflows affected: Governance / Sprint Review.
Risks identified: Incomplete data (if logs aren't structured enough) might lead to generic advice.

## Test Strategy
- **Unit Tests**:
    - Metric calculation logic on a set of dummy stories.
    - AI prompt generation verification (ensure no leaked secrets in prompt construction).
- **Integration Tests**:
    - Run on the current repo history with `--days 1` and verify report/json creation.

## Rollback Plan
- Delete the command and `reports/` directory.
