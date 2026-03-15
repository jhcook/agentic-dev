# INFRA-138: Canonical CWD Path Resolution

## State

COMMITTED

## Problem Statement

All `agent` CLI commands execute from `.agent/` (via `cd .agent && uv run agent ...`) but runbook paths, file references, and governance gates use repo-root-relative paths (e.g. `.agent/src/agent/commands/runbook.py`). This causes paths to resolve as `.agent/.agent/src/...` — which don't exist. There is no single canonical path resolution strategy; some code assumes CWD is repo root, other code assumes CWD is `.agent/`.

This has caused repeated, cascading failures:

1. **`agent implement`**: Cannot find target files for search/replace blocks — all `[MODIFY]` operations fail with "file not found".
2. **`ModifyBlock` Pydantic validator** (INFRA-134): AC-4(c) parent directory existence check failed because `Path(relative_path).parent.exists()` is CWD-dependent. Had to remove the check as a workaround, weakening validation.
3. **`agent preflight`**: QA validation gate fails with `cd .agent/src: No such file or directory` because test commands assume repo root CWD.
4. **`agent new-runbook`**: Generated runbooks with repo-root-relative paths that the implement command then can't resolve.

This is a systemic reliability problem that undermines the entire agentic workflow.

## User Story

As a developer using the agent CLI, I want all path resolution to be deterministic and CWD-independent so that `agent implement`, `agent preflight`, and validators work reliably regardless of how the CLI is invoked.

## Acceptance Criteria

- [ ] **AC-1: Canonical resolver**: A single `resolve_repo_path(relative: str) -> Path` utility exists in `agent.core.config` (or similar) that resolves any repo-relative path against `config.repo_root`, never against CWD.
- [ ] **AC-2: Implement integration**: `agent implement` uses the canonical resolver for all file operations (MODIFY, NEW, DELETE blocks). Files are found regardless of CWD.
- [ ] **AC-3: Validator integration**: `ModifyBlock`, `NewBlock`, and `DeleteBlock` validators use the canonical resolver. Re-enable parent directory existence check (AC-4(c) from INFRA-134) using `config.repo_root`.
- [ ] **AC-4: Preflight integration**: All governance gate commands (QA validation, security scan, etc.) resolve working directories via `config.repo_root`, not relative `cd` commands.
- [ ] **AC-5: Runbook path normalization**: `agent new-runbook` ensures all generated paths are repo-root-relative and validated against the canonical resolver.
- [ ] **AC-6: Test coverage**: Unit tests verify that the resolver works correctly when CWD is repo root, `.agent/`, a subdirectory, or `/tmp/`.
- [ ] **AC-7: Negative test**: Attempting to resolve a path with `..` traversal or absolute path raises `ValueError`.

## Non-Functional Requirements

- **Reliability**: Zero path resolution failures due to CWD mismatch.
- **Backward compatibility**: Existing runbooks and paths continue to work.
- **Observability**: Log a warning when a path would have resolved differently under the old CWD-dependent behavior (migration aid).

## Linked Journeys

- JRN-062: Implement Oracle Preflight Pattern

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight

## Linked Plans

- INFRA-135: Dynamic Rule Retrieval — Rule Diet (parent story that surfaced this bug)

## Impact Analysis Summary

Components touched: `agent.core.config`, `agent.core.implement.models`, `agent.core.implement.orchestrator`, `agent.commands.implement`, `agent.core.check/*` governance gates
Workflows affected: `/implement`, `/preflight`, `/runbook`, `/pr`
Risks identified: Must not break existing runbook paths — need backward-compatible resolution.

## Test Strategy

- Unit test: `resolve_repo_path("agent/src/foo.py")` returns `config.repo_root / "agent/src/foo.py"` regardless of `os.getcwd()`.
- Unit test: `resolve_repo_path("../escape/attempt")` raises `ValueError`.
- Integration test: `agent implement` succeeds on a runbook with `.agent/src/...` paths when CWD is both repo root and `.agent/`.
- Regression test: Re-enable `ModifyBlock` parent directory check and verify it passes for valid paths from any CWD.

## Rollback Plan

Revert the `resolve_repo_path` utility and restore CWD-dependent behavior. Existing workarounds (removed parent check) remain as fallback.

## Copyright

Copyright 2026 Justin Cook
