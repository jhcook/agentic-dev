# WEB-006: Operations Center

## State

OPEN

## Problem Statement

Managing secrets and monitoring the synchronization status of the agent requires manual CLI commands, which lack visibility and ease of use. Developers need a central place to view operational health.

## User Story

As a User, I want an Operations Center to manage secrets and view sync status visually, so that I can ensure the agent is operating correctly and securely without dropping to the terminal.

## Acceptance Criteria

- [ ] **Secrets Manager**: UI to list, set, and delete secrets (leveraging `agent secret`). Values should be masked by default.
- [ ] **Sync Dashboard**: Visual indicator of local vs remote artifact sync status (`agent sync status`).
- [ ] **Model Registry**: Visual list of available AI models and their capabilities (`agent list-models`).

## Linked ADRs

- ADR-009 (Agent Console Architecture)
- ADR-006 (Encrypted Secret Management)
