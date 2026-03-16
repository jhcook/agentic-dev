# INFRA-1028: Parser Robustness & Path Escaping

## State

COMMITTED

## Problem Statement

The current documentation parser incorrectly handles nested markdown structures and file system paths. Specifically, nested triple-backticks in Architecture Decision Records (ADRs) cause premature block closure, and paths containing underscores (e.g., `__init__.py`) are erroneously rendered as bold text, corrupting technical documentation.

Parent: INFRA-147

## User Story

As a **Developer**, I want the **documentation parser to correctly handle nested code fences and preserve file paths** so that **technical documentation remains accurate and readable.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a markdown file with nested code fences, When the parser processes the content, Then it must use balanced detection to prevent premature closure and preserve the inner backticks.
- [ ] **Scenario 2**: Headers containing special characters (`_`, `*`, `[`, `]`) must be automatically unescaped during extraction to ensure plain-text accuracy.
- [ ] **Negative Test**: System handles malformed or unclosed code fences gracefully without crashing the build pipeline.

## Non-Functional Requirements

- **Performance**: Parsing speed should maintain a sub-second response time for files under 50KB.
- **Security**: Implement path escaping to prevent markdown injection.
- **Compliance**: Documentation must meet internal standards for technical accuracy.
- **Observability**: Add debug logging for regex matching failures in the header extraction layer.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Impact Analysis Summary

- **Components touched**: `parser.py`, Markdown rendering utilities.
- **Workflows affected**: Automated documentation generation, ADR publishing.
- **Risks identified**: Potential for regex "catastrophic backtracking" if non-greedy patterns are not strictly bounded.

## Test Strategy

- **Unit Testing**: Validate `parser.py` regex against a suite of strings containing nested backticks and complex file paths (e.g., `src/module/__init__.py`).
- **Regression Testing**: Ensure existing standard markdown files parse identically to previous versions.
- **Integration Testing**: Execute a full documentation build of the current ADR repository to verify visual layout.

## Rollback Plan

- Revert changes to `parser.py` via Git.
- Redeploy the previous stable version of the documentation service.

## Copyright

Copyright 2026 Justin Cook
