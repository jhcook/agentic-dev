# INFRA-046: Secure Secret Rotation

## State

COMMITTED

## Problem Statement

The current Secret Manager implementation lacks two critical security features:

1. **Safety**: It allows re-initialization (generating a new master key) even if encrypted secret files exist. This orphans the existing secrets, making them undecryptable and effectively causing data loss.
2. **Rotation**: It does not support rotating the master password. Users cannot change their password without deleting all secrets and starting over.

## User Story

As a Developer using the Agent CLI, I want to be able to safely rotate my master password and prevent accidental re-initialization, so that I can maintain security hygiene without losing access to my stored credentials.

## Acceptance Criteria

- [ ] **Init Safety**: `env -u VIRTUAL_ENV uv run agent secret init` MUST fail if valid secret files (`*.json`) exist but `config.json` is missing (or if user tries to re-init), improving robustness against accidental resets.
  - Error message must guide user to either use `--force` or checking status.
- [ ] **Key Rotation**: `env -u VIRTUAL_ENV uv run agent secret rotate-key` command is implemented.
  - Prompts for CURRENT password (validation required).
  - Prompts for NEW password (with strength check).
  - Re-encrypts ALL stored secrets with the new key.
  - Updates system keychain if applicable.
- [ ] **Verification**: Old password no longer works; new password unlocks and decrypts secrets.
- [ ] **Data Safety**:
  - Rotation automatically creates a backup of `secrets/` before starting.
  - If rotation fails (e.g., crash), the original state is preserved (atomic operation).

## Non-Functional Requirements

- **Security**: Master password must never be logged or stored in plain text (except transiently in memory during rotation).
- **Usability**: Clear error messages when user attempts unsafe actions.
- **Reliability (Atomicity)**: The rotation process must use a transaction-like approach (e.g., work on temp files, then swap) to ensure no data loss on failure.

## Linked ADRs

- ADR-017-agent-cli-command-registry.md

## Impact Analysis Summary

Components touched:

- `agent.core.secrets`: `initialize` logic, new `change_password` method.
- `agent.commands.secret`: `init` command update, new `rotate-key` command.

## Test Strategy

- Unit tests for `SecretManager.change_password`.
- Integration test for `init` safety guard (mocking file system).
- Manual verification of rotation flow.
- **Chaos Testing**: Verify data integrity if rotation is interrupted (SIGINT/Ctrl+C).

## Rollback Plan

- Revert changes to `agent.core.secrets` and `agent.commands.secret`.
- If a rotation fails mid-operation, the system might be in a mixed state. The implementation should ideally be atomic or atomic-like (backup `config.json` before switch).
