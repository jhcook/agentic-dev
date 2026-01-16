# INFRA-008: Finalize Agent CLI Functionality

## State
COMMITTED

## Related Story
INFRA-009
INFRA-010
INFRA-011
INFRA-012
INFRA-013

## Child Stories
- [INFRA-009: Implement UI Tests Runner](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-009-implement-ui-tests.md)
- [INFRA-010: Enhance Implement Command](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-010-enhance-implement-command.md)
- [INFRA-011: Improve Impact Analysis](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-011-improve-impact-analysis.md)
- [INFRA-012: Refactor Codebase Utilities](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-012-refactor-codebase.md)
- [INFRA-013: Optimize Sync for Large Datasets](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-013-optimize-sync.md)

## Summary
The `agent` CLI has several stubbed or incomplete commands that require finalization to be fully "agentic" and useful in a production workflow. This plan outlines the work to implement the missing pieces, specifically the UI test runner integration, active implementation capabilities, and improved static analysis.

## Objectives
- **Implement `run-ui-tests`**: Replace the stub with a functional test runner integration using **Maestro** (executing YAML flows in `tests/ui`).
- **Enhance `implement`**: Upgrade the `agent implement` command from a passive advisor to an active coder that can optionally apply generated diffs to the codebase, with safety checks.
- **Improve `impact`**: Expand the reported static analysis in `agent impact` to include actual dependency graph traversal for Python and JS/TS files, rather than just "TBD".
- **Refactor Codebase**: Consolidate utility functions (like `find_story_file`) to `agent.core.utils` to remove duplication and improve maintainability.
- **Sync Optimization**: Add pagination or chunking to `agent sync` to handle larger histories.

## Verification
- **Code Review**: All changes pass preflight checks with strict linting.
- **Manual Testing**:
    - Run `agent run-ui-tests` and verify it triggers `maestro test`.
    - Run `agent implement` on a dummy runbook and verify code is applied.
    - Run `agent impact` on a known change and verify the output lists affected components accurately without AI.
- **Automated Tests**: New unit tests for the enhanced commands.

## Execution Log
- **INFRA-009**: Implemented `agent run-ui-tests` using Maestro CLI. Verified with unit tests and mocks. Status: COMPLETED.

