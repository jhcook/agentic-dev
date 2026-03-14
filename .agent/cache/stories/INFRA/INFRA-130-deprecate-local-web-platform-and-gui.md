# INFRA-130: Icebox Local Web Platform and GUI

## State

COMMITTED

## Problem Statement

The Local Web Platform (Admin Console GUI via React) adds weight to the core engine, but contains valuable work that should be preserved as a future addon.

## User Story

As a **Platform Developer**, I want to **icebox the Local Web Admin Console** so that **it is removed from the active context but preserved for a future plugin/addon system**.

## Acceptance Criteria

- [ ] **Scenario 1**: Given the cache state, When the stories are analyzed, Then `WEB-004`, `WEB-005` and `WEB-006` are marked as `ICEBOX`.
- [ ] **Scenario 2**: Journeys `JRN-049` and `JRN-050` are marked as `ICEBOX`.
- [ ] **Negative Test**: No source files in `.agent/src/` are modified or deleted in this ticket.

## Non-Functional Requirements

- Performance: Zero latency impact, only documentation changes.
- Security: Reduces attack surface by disabling UI code integration goals.
- Compliance: N/A
- Observability: N/A

## Linked ADRs

- ADR-009

## Linked Journeys

- JRN-088

## Impact Analysis Summary

Components touched: `.agent/cache/stories/WEB`
Workflows affected: Console UI navigation
Risks identified: N/A - Solely state changes.

## Test Strategy

Visual inspection of Markdown frontmatter and git diffs before merging.

## Rollback Plan

Revert git commit on documentation changes.

## Copyright

Copyright 2026 Justin Cook
