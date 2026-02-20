# INFRA-068: Align `/impact` Workflow with `agent impact` CLI

## State

COMMITTED

## Problem Statement

The `/impact` workflow instructs the AI agent to "manually perform the impact analysis" — running git diff, reading story files, invoking the `DependencyAnalyzer`, constructing AI prompts, and optionally updating story files. This logic duplicates what `agent impact` should do. The CLI command exists but the workflow bypasses it, violating the core philosophy that logic should be encapsulated in CLI commands.

## User Story

As a developer using `/impact`, I want the workflow to simply call `agent impact` and review the output, so that impact analysis logic is maintained in one place (the CLI) rather than duplicated across workflow instructions.

## Acceptance Criteria

- [ ] **AC1: Full Analysis**: `agent impact` performs static dependency analysis AND AI-powered risk assessment in a single invocation.
- [ ] **AC2: Story Update**: `agent impact --update-story` automatically injects the analysis into the story's "Impact Analysis Summary" section.
- [ ] **AC3: Base Branch**: `agent impact --base main` compares against a specific branch (currently documented in workflow but not in CLI).
- [ ] **AC4: Structured Output**: Output includes dependency metrics, risk assessment, and recommendations in a parseable format.
- [ ] **AC5: Workflow Simplification**: The `/impact` workflow is reduced to calling `agent impact` with appropriate flags.
- [ ] **Negative Test**: When no changes are detected, the CLI reports cleanly and exits 0.

## Non-Functional Requirements

- **Performance**: Analysis should complete within 60s for typical changesets.
- **Observability**: Log dependency graph size and AI prompt size at DEBUG level.

## Linked ADRs

- ADR-025 (Lazy Initialization)
- ADR-030 (Workflow-Calls-CLI Pattern — to be created)

## Linked Journeys

- JRN-057 (Impact Analysis Workflow)

## Impact Analysis Summary

Components touched: `check.py` (impact command), `impact.md` workflow
Workflows affected: `/impact`
Risks identified: Existing `agent impact` may need significant refactoring to absorb manual workflow logic.

## Test Strategy

- **Unit test**: Verify `agent impact` calls `DependencyAnalyzer` and returns structured output.
- **Unit test**: Verify `--update-story` modifies the story file correctly.
- **Integration test**: Run `agent impact` with staged changes and validate output format.

## Rollback Plan

Revert CLI changes. Workflow can remain as manual fallback.
