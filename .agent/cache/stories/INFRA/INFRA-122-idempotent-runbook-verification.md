# INFRA-122: Idempotent Runbook Verification

## State

DRAFT

## Problem Statement

LLMs frequently generate runbooks containing "hallucinated" code blocks or incorrect context within search markers. When these `<<<SEARCH/===/>>>` blocks fail to find an exact match in the target codebase, the runbook execution fails, requiring manual intervention and decreasing the reliability of automated remediations.

## User Story

As a **DevOps Engineer**, I want **the system to dry-run and verify runbook search blocks before acceptance** so that **hallucinations are caught and corrected automatically by the LLM, ensuring idempotent and successful execution.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a generated runbook with valid search blocks, When the verification gate dry-runs the blocks against the source, Then the runbook is marked as "Verified" and proceeds to the execution queue.
- [ ] **Scenario 2**: Given a search block that does not match the source file, When the dry-run fails, Then the system must return the specific error and the relevant file context back to the LLM for an automated rewrite.
- [ ] **Negative Test**: System handles persistent hallucinations gracefully by terminating the loop and alerting the user if the LLM fails to produce a valid search block after three (3) rewrite attempts.

## Non-Functional Requirements

- **Performance**: The dry-run verification gate must add less than 2 seconds of overhead to the total generation workflow.
- **Security**: File source context passed back to the LLM must be filtered for secrets and PII.
- **Compliance**: All verification failures and subsequent LLM correction prompts must be stored in the audit trail.
- **Observability**: Expose metrics for "Verification Success Rate" and "LLM Rewrite Cycles" to monitor prompt drift.

## Linked ADRs

- ADR-104: Runbook Verification Strategy

## Linked Journeys

- JRN-022: Automated Incident Remediation

## Impact Analysis Summary

- **Components touched**: Runbook Execution Engine, LLM Orchestration Layer, File System Provider.
- **Workflows affected**: Runbook generation, automated patching, and CI/CD deployment hooks.
- **Risks identified**: Potential for infinite feedback loops (mitigated by retry limits) and increased token consumption costs.

## Test Strategy

Verification will be validated using a suite of "Synthetic Hallucination" test cases where search blocks are intentionally skewed. We will measure the system's ability to identify the mismatch and the LLM's success rate in correcting the block based on the provided error feedback.

## Rollback Plan

Disable the verification gate via the `ENABLE_RUNBOOK_GATE` feature flag, reverting the system to direct execution mode (standard error handling).

## Copyright

Copyright 2026 Justin Cook