# INFRA-020: Implement Agent Audit

## State
COMMITTED

## Problem Statement
While `env -u VIRTUAL_ENV uv run agent check` provides quick pre-flight verification, we lack a tool for deep-dive governance audits. We cannot easily answer questions like "Is every line of code traceable to a Story?" or "Do we have 'Stagnant Code' that hasn't been touched in forever?" or "Are there files not owned by any governance artifact?". This makes it hard to maintain strict "Governance as Code" over the long term.

## User Story
As a Compliance Officer or Lead Dev, I want to run `env -u VIRTUAL_ENV uv run agent audit` to perform an exhaustive scan of the repository, verifying traceability and identifying substantial governance gaps, so that I can generate a compliance report for stakeholders.

## Acceptance Criteria
- [ ] **Traceability Scan**: The command scans all source files and attempts to match them to a Story or Runbook (via `agent_state` or file headers). Reports % of "Ungoverned Files".
- [ ] **Stagnant Code**: Identifies files that have not been modified in > X months (default 6) and are not linked to recent active stories. *Renamed from 'Zombie Code'.*
- [ ] **Orphaned Artifacts**: Identifies "Open" stories/plans that have had no activity for > 30 days. **Logic update**: Must exclude items that are blocked by other active dependencies.
- [ ] **Report Generation**: Outputs `AUDIT-<Date>.md` with a summary of health scores (Traceability %, Stagnant Count, Orphan Count) and lists the *Top 10 Worst Offenders*.
- [ ] **Exclusions**: Respects `.gitignore` and an optional `.auditignore` for things like legacied code.
- [ ] **CI Integration**: Supports a `--fail-on-error` or `--min-traceability <int>` flag to exit with non-zero code if health is poor.

## Non-Functional Requirements
- **Performance**: The audit is a "Batch" job (1-2 mins OK). **Must** use stream/iterative processing to avoid OOM on large repos.
- **Resilience**: Must gracefully handle permission errors (log warning and continue).
- **Readability**: The report must be understandable by non-technical stakeholders (high-level red/green indicators).

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/audit.py` (new), `agent/core/governance.py` (new).
Workflows affected: Quarterly Planning / Governance Audits.
Risks identified: False positives on "Ungoverned Files" if traceability logic is too strict.

## Test Strategy
- **Unit Tests**:
    - "Stagnant Code" detector date math.
    - Traceability logic (mocking file existence and runbook content).
- **Integration Tests**:
    - Run on current repo and verify report structure.
    - Test `--min-traceability` triggers failure on a deliberately bad repo state.

## Rollback Plan
- Delete the command file.

