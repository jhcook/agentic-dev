# INFRA-076: Create binary release using end-user license

## State

COMMITTED

## Problem Statement

Currently, the agent's binary release process doesn't respect the end-user's LICENSE file, potentially leading to licensing conflicts and compliance issues.

## User Story

As a developer, I want the `package.sh` and `release.sh` scripts to build a binary release of the agent using PyInstaller that respects the end-user's LICENSE file, so that we ensure compliance and avoid licensing conflicts.

## Acceptance Criteria

- [ ] **Scenario 1**: Given a valid LICENSE file in the project root, When `package.sh` and `release.sh` are executed, Then the resulting binary release includes and respects the provided LICENSE.
- [ ] **Scenario 2**: The binary should display the end-user's LICENSE information when a designated command-line flag (e.g., `--license`) is used.
- [ ] **Negative Test**: When no LICENSE file is present, the build process should fail gracefully with a clear error message, preventing a release with our default license.

## Non-Functional Requirements

- **Performance:** Build process should remain within acceptable time limits (defined in ADR-XXX).
- **Security:** The LICENSE inclusion process should not introduce any security vulnerabilities.
- **Compliance:** Ensure the process aligns with open-source licensing requirements.
- **Observability:** Build process logs should clearly indicate whether the LICENSE inclusion was successful.

## Linked ADRs

- ADR-001 (Example: Documenting build process decisions)

## Linked Journeys

- JRN-001 (Example: New Release Process)

## Impact Analysis Summary

Components touched: `package.sh`, `release.sh`, PyInstaller configuration
Workflows affected: Binary release process
Risks identified: Potential for breaking existing build processes, incorrect license attribution.

## Test Strategy

- Unit tests for the updated scripts to ensure correct license handling.
- End-to-end tests to verify the generated binary includes the correct license information.
- Manual inspection of the binary release for LICENSE verification.

## Rollback Plan

- Revert the changes to `package.sh` and `release.sh` to the previous version using Git.
- Re-run the build process to create a binary release with the original license handling.

## Copyright

Copyright 2026 Justin Cook
