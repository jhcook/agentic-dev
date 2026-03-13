# INFRA-127: Fix broken tests

## State

COMMITTED

## Problem Statement

Various tests broke due to recent validation additions. The main branch has test failures that prevent preflight checks from passing on subsequent work.

## User Story

As a developer I want the test suite to pass on main so that I can rely on CI/CD and preflight checks.

## Acceptance Criteria

- [ ] `test_implement_updates_journey.py` passes via `agent implement` mock runbook corrections.
- [ ] `agent preflight` passes on this story branch with the test fixes.

## Non-Functional Requirements

N/A

## Linked ADRs

N/A

## Linked Journeys

- JRN-009

## Impact Analysis Summary

Fixes broken tests in `test_implement_updates_journey`.

## Test Strategy

Run `pytest .agent/tests`.

## Rollback Plan

Revert the commit.

## Copyright

Copyright 2026 Justin Cook
