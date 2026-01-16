# Runbook: File-Based Versioning System (INFRA-006)

**Status**: ACCEPTED
**Story**: [INFRA-006](.agent/cache/stories/INFRA/INFRA-006-file-based-versioning-system.md)
**Assignee**: @Backend

## Context
The `agent` CLI needs to report its version correctly even when distributed as a tarball without `.git` metadata. We will implement a file-based fallback mechanism.

## Proposed Changes

### 1. Build Script (`package.sh`)
- **Objective**: Generate a `VERSION` file during packaging.
- **Action**: Add a step to `package.sh` that runs `git describe --tags --always --dirty > VERSION` before archiving.

### 2. CLI Entrypoint (`.agent/src/agent/main.py`)
- **Objective**: Read from `VERSION` file if git lookup fails.
- **Action**:
    - Locate the integration point for version retrieval.
    - Add logic to check for a `VERSION` file in the package root (adjacent to `main.py` or package root).
    - If `VERSION` exists, return its content.
    - Fallback to "unknown" or existing default.

## Verification Plan

### Manual Verification
1. **Dev Mode**: Run `agent --version` in the repo -> Expect `git describe` output.
2. **Dist Mode**:
    - Run `./package.sh`.
    - Extract the tarball to a temporary location (outside git).
    - Run the extracted `agent` -> Expect `VERSION` file content.

### Automated Tests
- Ensure `test_governance.py` and other new tests pass.
- (Optional) Add a unit test specifically for the version reader function mocking the file system.
