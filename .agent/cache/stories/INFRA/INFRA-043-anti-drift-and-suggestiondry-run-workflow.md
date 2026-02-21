# STORY-INFRA-043: Anti-Drift and Suggestion/Dry-Run Workflow

## State

COMMITTED

## Problem Statement

The agent currently makes unsolicited "cleanup" changes (like replacing `print` with `logging`, or reformatting code) during implementation tasks. This "drift" degrades the user experience and can break CLI output functionality. Users need a way to review these suggestions (Dry Run) and Opt-In to them, rather than having them forced.

## User Story

As a Developer,
I want the Agent to ONLY implement what is explicitly requested, but still suggest improvements,
So that I can maintain control over the codebase while benefitting from AI insights.

## Acceptance Criteria

- [x] **Anti-Drift Rule**: A new rule (`.agent/rules/anti-drift.mdc`) explicitly forbids unsolicited changes ("Ask, Don't Touch").
- [x] **Suggestion Workflow**: The Runbook template includes a "Proposed Improvements (Opt-In)" section.
- [x] **Dry Run Support**: `env -u VIRTUAL_ENV uv run agent implement <ID>` (without --apply) serves as a preview/dry-run.
- [x] **ADR-016**: Architecture Decision Record establishes `print()` as valid for CLI output.
- [x] **Linter Config**: `ruff` is configured to ignore rule T201 (print found) in CLI directories to reduce confusion.

## Impact Analysis

- **Governance**: Adds strict scoping rules.
- **Workflow**: alters the Runbook creation and Implementation review flow.
- **Risk**: Low (Documentation and Coniguration only).

## Test Strategy

- Manual: Create a Runbook with a suggestion, leave it unchecked, verify `env -u VIRTUAL_ENV uv run agent implement` does not apply it.
- Manual: Check it, verify `env -u VIRTUAL_ENV uv run agent implement` applies it.

## Non-Functional Requirements

## Impact Analysis Summary

## Rollback Plan