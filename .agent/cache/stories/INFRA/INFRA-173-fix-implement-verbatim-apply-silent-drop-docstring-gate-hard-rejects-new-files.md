# INFRA-173: Fix implement verbatim-apply silent drop: docstring gate hard-rejects [NEW] files

## State

COMMITTED

## Problem Statement

The `verbatim-apply` workflow in Phase 1 of the implementation engine hard-rejects new files (`[NEW]`) if they contain function-level docstring gaps that cannot be automatically resolved. This current behavior incorrectly blocks `test_*.py` files (which typically do not require docstrings) and utility files with missing `__init__` docstrings. These rejections are handled silently by adding files to a `rejected_files` list and displaying a misleading "INCOMPLETE IMPLEMENTATION" banner, hindering development velocity and providing poor feedback to the user.

## User Story

As a developer, I want the agent to apply new files even if they have minor docstring violations so that I can review the implementation and address linting/documentation gaps during the preflight or refinement stage rather than having my work silently discarded.

## Acceptance Criteria

- [x] **Scenario 1**: Given a new file named `test_utility.py`, When the `verbatim-apply` engine processes it, Then the docstring gate must be bypassed regardless of function-level documentation presence.
- [x] **Scenario 2**: Given a new file `token_counter.py` with a missing `__init__` docstring, When the engine runs, Then the file must be written to the filesystem and the violation downgraded to a warning.
- [x] **Scenario 3**: The "INCOMPLETE IMPLEMENTATION" banner must only trigger for critical application failures, not for files that were successfully written with docstring warnings.
- [x] **Negative Test**: System handles non-existent file paths or filesystem permission errors gracefully without attributing them to docstring violations.

## Non-Functional Requirements

- **Observability**: Docstring gaps must be clearly logged as warnings in the CLI output rather than silent entries in a rejection list.
- **Compliance**: Ensure that while the gate is downgraded to a warning, the gaps are still surfaced to the user to maintain long-term code quality standards.

## Linked ADRs

- ADR-012: Implementation Gate Strategy

## Linked Journeys

- JRN-004: Automated Feature Implementation

## Impact Analysis Summary

### Core Deliverables (In-Scope)

| Status | File | Change Summary |
| :--- | :--- | :--- |
| `MODIFIED` | `.agent/src/agent/commands/implement.py` | Phase 1 verbatim-apply loop updated: test file detection expanded, docstring violations downgraded to `WARNING`, `_display_implementation_summary()` helper added |
| `MODIFIED` | `.agent/src/agent/commands/gates.py` | `GateStatus` enum added; `TEST_FILE_PATTERNS: List[str]` constant defined |
| `MODIFIED` | `.agent/src/agent/utils/validation_formatter.py` | `format_implementation_summary()` added — renders tri-state (SUCCESS / SUCCESS WITH WARNINGS / INCOMPLETE) `rich` panel |
| `ADDED` | `.agent/src/agent/utils/path_security.py` | New module — `is_test_file_secure()` secure path anchoring to prevent traversal-based docstring gate bypasses |
| `ADDED` | `.agent/docs/implementation-engine.md` | New documentation — validation severity levels and test file exclusion patterns |

### Tests Added (In-Scope)

| Status | File | Coverage |
| :--- | :--- | :--- |
| `ADDED` | `.agent/tests/agent/core/implement/test_path_security.py` | `is_test_file_secure` — traversal anchoring, pattern coverage, case insensitivity, edge cases |
| `ADDED` | `.agent/tests/gates/test_docstring_validator.py` | `DocstringValidator` — bypass logic, downgrade-to-warning, path anchoring, error handling |
| `ADDED` | `.agent/tests/implement/test_engine.py` | `ImplementationEngine.get_verdict()` — SUCCESS WITH WARNINGS vs INCOMPLETE |
| `ADDED` | `.agent/tests/implement/test_verbatim_apply.py` | `VerbatimApplier.apply()` — file is written even when WARNING status returned |

### Co-commits (Out-of-Scope Changes on This Branch)

| Status | File | Reason |
| :--- | :--- | :--- |
| `MODIFIED` | `.agent/src/agent/commands/runbook_generation.py` | Incidental fix applied during debugging session |
| `MODIFIED` | `.agent/src/agent/core/tests/test_guardrails.py` | Guardrail test update applied as part of preflight autoheal |
| `MODIFIED` | `CHANGELOG.md` | Auto-updated by `agent commit` |
| `MODIFIED` | `.agent/cache/journeys/INFRA/JRN-004-distributed-cache-synchronization-with-sqlite-and-supabase.yaml` | Auto-linked by implementation engine |

### Workflows Affected

- `agent implement` Phase 1 (file application and gate evaluation)
- Automated preflight check reporting

### Risks

- Increased technical debt if developers ignore docstring warnings surfaced at preflight stage.

## Test Strategy

- **Unit Testing**: Update `tests/gates/test_docstring_validator.py` to verify that filename-based exclusion (pytest convention) works correctly.
- **Integration Testing**: Execute `agent implement` with a mock plan containing a new test file and a source file with missing docstrings; verify both are written to the workspace and the command exits with a success/warning status.
- **Regression Testing**: Ensure syntax errors in new files still trigger appropriate hard-rejections where applicable.

## Rollback Plan

- Revert changes to `.agent/src/gates/docstring_validator.py` and `.agent/src/implement/verbatim_apply.py` to restore strict enforcement.
- Verification of rollback via existing gate test suite.

## Copyright

Copyright 2026 Justin Cook
