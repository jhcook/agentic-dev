# INFRA-067: Enhance `env -u VIRTUAL_ENV uv run agent implement` with Post-Apply Governance Gates

## State

IN_PROGRESS

## Problem Statement

The `env -u VIRTUAL_ENV uv run agent implement` CLI command handles pre-validation (runbook status, branch management, journey gate) and AI code generation, but does not programmatically enforce the post-apply governance phases defined in the `/implement` workflow. Phases 3 (Security Scan), 4 (QA Validation), 5 (Documentation Check), and 6 (Completion Sync with structured verdict) are entirely left to the AI agent reading the workflow markdown. This means governance is advisory, not enforced.

Core philosophy violation: logic that should be encapsulated in Python CLI commands is instead embedded in workflow instructions for the agent.

## User Story

As a developer using `env -u VIRTUAL_ENV uv run agent implement`, I want the CLI to automatically run security scans, execute tests, and verify documentation after applying code changes, so that governance gates are enforced programmatically rather than relying on the AI agent's interpretation of workflow instructions.

## Acceptance Criteria

- [ ] **AC1: Composable Gate Module**: Post-apply phases are implemented in a new `gates.py` module with composable functions (`run_security_scan()`, `run_qa_gate()`, `run_docs_check()`), not inlined in `implement.py`.
- [ ] **AC2: Security Scan**: Given `--apply` is used, when code is generated, then the CLI scans the AI output using patterns from `.agent/etc/security_patterns.yaml` (API keys, `eval()`, `exec()`, PII) before applying.
- [ ] **AC3: Configurable QA Gate**: Given `--apply` is used, when code is applied, then the CLI executes the test command configured in `.agent/etc/agent.yaml` (`test_command` key, default: `make test`). Non-zero exit code blocks.
- [ ] **AC4: Docs Check**: Given `--apply` is used, when Python files are modified, then the CLI verifies that new/modified top-level functions have docstrings.
- [ ] **AC5: Structured Verdict**: After all phases complete, the CLI outputs a per-phase summary with APPROVE/BLOCK verdict and timing (e.g., `[PHASE] Security Scan ... PASSED (1.2s)`).
- [ ] **AC6: Skip Flags with Audit Logging**: `--skip-journey-check`, `--skip-tests`, and `--skip-security` flags exist. Each logs a timestamped warning to stdout: `⚠️ [AUDIT] Security gate skipped at 2026-02-19T23:44:45`.
- [ ] **AC7: Workflow Alignment**: After enhancement, the `/implement` workflow can be reduced to primarily calling `env -u VIRTUAL_ENV uv run agent implement` with appropriate flags.
- [ ] **Negative Test**: Security scan blocks when `eval(user_input)` is detected in AI output.

## Non-Functional Requirements

- **Performance**: Post-apply phases should add < 30s (excluding test execution time).
- **Security**: Security patterns defined in `security_patterns.yaml`, not hardcoded. PII detection does not log or persist detected PII, only reports presence.
- **Compliance**: All `--skip-*` overrides produce audit trail entries.
- **Observability**: Each phase emits structured console output with timing. Supports `--json` output for CI integration.

## Linked ADRs

- ADR-025 (Lazy Initialization)
- ADR-028 (Synchronous CLI Design)
- ADR-030 (Workflow-Calls-CLI Pattern — to be created)

## Linked Journeys

- JRN-056 (Full Implementation Workflow)

## Impact Analysis Summary

Components touched: `implement.py`, new `gates.py`, new `security_patterns.yaml`, `agent.yaml`
Workflows affected: `/implement`
Risks identified: False positives in security scan (mitigated by externalized patterns); `make test` may not exist (mitigated by configurable test command).

## Test Strategy

- **Unit test**: `test_implement_skip_journey_check` — verify `--skip-journey-check` bypasses journey gate and logs audit warning.
- **Unit test**: `test_implement_security_scan_blocks` — verify security scan catches `eval()` or API keys in AI output.
- **Unit test**: `test_implement_qa_runs_tests` — verify configured test command is called when `--apply` is used.
- **Unit test**: `test_gates_composable` — verify `gates.py` functions work independently and in combination.
- **Integration test**: End-to-end `/implement` workflow regression after Phase 1.
- **Existing tests**: All 6 existing tests in `test_implement.py` must continue to pass.

## Rollback Plan

Revert changes to `implement.py` and remove `gates.py`. The enhancements are additive — removing the post-apply phases returns to the current behavior.
