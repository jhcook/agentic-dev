# INFRA-163: Preflight Autoheal: Per-Role Autonomous Correction Loop

## State

REVIEW_NEEDED

## Problem Statement

Preflight failures with a `BLOCK` verdict currently require manual intervention, even when the required fix is clearly stated in the panel report. Similarly, unit test failures in the `🧪 Running Automated Tests` phase require the developer to read the traceback, identify the fix, and re-run manually. Both failure modes slow down the implementation loop with mechanical, automatable work.

## User Story

As a **Developer or DevOps Engineer**, I want the **preflight tool to autonomously fix blocking governance violations and test failures** so that I can **remediate compliance issues rapidly and ensure a clean path to deployment with minimal manual effort.**

## Acceptance Criteria

- [ ] **AC-1 (Governance Heal)**: Given `--autoheal`, when a role returns `VERDICT: BLOCK`, the system extracts `REQUIRED_CHANGES`, applies surgical AI-assisted edits to source files, stages them with `git add`, and re-runs governance in a new cycle.
- [ ] **AC-2 (Test Heal)**: Given `--autoheal`, when the automated test phase fails, the system streams the test run live, then re-runs with capture to extract the traceback, identifies the failing source file(s), applies AI-assisted fixes, stages them, and re-runs only the affected test command.
- [ ] **AC-3 (Shared Budget)**: The `PreflightHealer` instance is created ONCE before the governance retry loop and its budget is shared across all roles and all governance cycles — preventing unbounded token spend. Default budget: 3 attempts total.
- [ ] **AC-4 (Staged-only)**: All autoheal edits are staged (`git add`) but never committed — the developer retains full control.
- [ ] **AC-5 (PII)**: PII scrubbing is applied to diffs and tracebacks before passing to the AI healer, consistent with the existing preflight scrubbing pipeline.
- [ ] **AC-6 (Stub Detection)**: A new DoD gate verifier `_gap_4i` (`check_stub_implementations`) validates that AI-generated code blocks do not contain placeholder code (`pass`, `raise NotImplementedError`, TODO/FIXME comments, stub phrases); any such block fails the gate.
- [ ] **AC-7 (Self-Protection)**: Both `PreflightHealer` and `TestHealer` include a `_PROTECTED_RE` guard that prevents them from overwriting `agent/core/preflight/healer.py` or `agent/core/preflight/test_healer.py` — preventing bootstrapping self-destruction.
- [ ] **Negative Test**: `WARN` verdicts do not trigger governance heal; budget exhaustion stops the loop immediately without re-running the full governance panel.

## Non-Functional Requirements

- **Performance**: Streaming test output so the terminal is live during test runs; captured only on failure for traceback extraction.
- **Security**: AI healer uses the existing PII scrubbing pipeline (`scrub_sensitive_data`) to ensure no sensitive data leaves the environment.
- **Compliance**: AI edits are "surgical" (minimal changes via [MODIFY] blocks) rather than wholesale file rewrites.
- **Observability**: Structured log events: `governance_healer_attempt`, `governance_healer_applied`, `governance_healer_budget_exhausted`, `governance_healer_protected_skip`, `test_healer_attempt`, `test_healer_fix_applied`, `test_healer_rerun_result`.

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight
- ADR-015: Interactive Preflight Repair
- ADR-022: Interactive Fixer Pattern
- ADR-029: ADK Multi-Agent Integration
- ADR-028: Typer Synchronous CLI Architecture

## Linked Journeys

- JRN-036: Implement Interactive Preflight Repair
- JRN-062: Implement Oracle Preflight Pattern

## Impact Analysis Summary

**Components touched:**
- `.agent/cache/runbooks/INFRA/INFRA-163-runbook.md` — **[NEW]** Implementation runbook describing all changes, file modifications, and acceptance criteria for INFRA-163.
- `.agent/src/agent/commands/check.py` — **[MODIFY]** Add `--autoheal` and `--budget` options; create `PreflightHealer` once before governance loop (shared budget); wire `TestHealer` into test execution path (stream live, capture on failure).
- `.agent/src/agent/core/preflight/healer.py` — **[NEW]** `PreflightHealer`: governance heal via REQUIRED_CHANGES extraction + AI [MODIFY] blocks + `git add` staging. Includes `_PROTECTED_RE` self-protection guard.
- `.agent/src/agent/core/preflight/test_healer.py` — **[NEW]** `TestHealer`: pytest traceback extraction via `_FILE_RE` + AI code-fence fix + `git add` staging + targeted re-run. Includes `_PROTECTED_RE` self-protection guard.
- `.agent/src/agent/commands/tests/test_preflight_autoheal.py` — **[NEW]** 16 unit tests covering: budget enforcement, shared budget, edit application, required_changes list normalisation, self-protection guard, PII scrubbing, test-file exclusion.
- `.agent/src/agent/core/implement/guards.py` — **[MODIFY]** Add `check_stub_implementations` (`_gap_4i`): detects `pass`, `raise NotImplementedError`, TODO/FIXME, and stub phrases in AI-generated code blocks. Add `check_op_type_vs_filesystem`: validates that `[MODIFY]`/`[DELETE]` paths exist on disk. Refactor `check_imports` to resolve `pyproject.toml` from `.agent/` when repo root has none.
- `.agent/src/agent/commands/runbook.py` — **[MODIFY]** Import and wire `_gap_4i` (`check_stub_implementations`) into Gate 4 `dod_gaps` list and `_gap_ids_list`.
- `.agent/src/agent/core/implement/tests/test_guards.py` — **[MODIFY]** Add unit tests for `check_stub_implementations` and `check_op_type_vs_filesystem`.
- `CHANGELOG.md` — **[MODIFY]** Document INFRA-163 changes: `--autoheal` flag, `PreflightHealer`, `TestHealer`, stub detection guard, self-protection mechanism.
- `.agent/cache/journeys/INFRA/JRN-036-implement-interactive-preflight-repair.yaml` — **[MODIFY]** Add `implementation.tests` entry linking `test_preflight_autoheal.py`.
- `.agent/cache/journeys/INFRA/JRN-062-implement-oracle-preflight-pattern.yaml` — **[MODIFY]** Add `implementation.tests` entries linking `test_preflight_autoheal.py`, `test_dod_compliance.py`, `test_dod_gate_orchestration.py`.

**Workflows affected:** Local developer preflight loop, CI/CD governance gate, runbook Gate 4 DoD compliance.

**Risks:** AI-generated regressions — mitigated by staged-only changes, self-protection guards, and budget cap. Autoheal cannot modify its own implementation files.

## Test Strategy

- **Unit Tests (16)**: Budget enforcement, shared budget across roles/cycles, [MODIFY] block parsing, `git add` staging, required_changes list→string normalisation, `_PROTECTED_RE` matching, PII scrubbing call order, test-file exclusion from `_extract_failing_files`, protected-file exclusion from `_extract_failing_files`.
- **Unit Tests (guards)**: `check_stub_implementations` — pass, NotImplementedError, TODO/FIXME, stub phrases, clean code.
- **Regression**: `WARN` verdicts do not trigger heal. Budget exhaustion stops loop before re-running governance panel. TestHealer never identifies `healer.py`/`test_healer.py` as fix targets.

## Rollback Plan

- **CLI Level**: Omit `--autoheal` flag to return to standard reporting behaviour.
- **Filesystem**: All autoheal edits are staged but not committed — `git restore --staged .` reverts all autoheal modifications instantly.

## Copyright

Copyright 2024-2026 Justin Cook
