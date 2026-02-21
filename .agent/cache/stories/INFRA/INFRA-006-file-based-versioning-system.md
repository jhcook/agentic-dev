# INFRA-006: File-Based Versioning System

## State
COMMITTED

## Problem Statement
The `agent` CLI currently lacks a robust versioning mechanism when running outside of a git repository. When users install the tool from a packaged distribution (e.g., tarball), running `env -u VIRTUAL_ENV uv run agent --version` often fails or returns a placeholder because `.git` metadata is missing. We need a system that supports both development (dynamic git versioning) and production distribution (static file versioning).

## User Story
As a developer or user of the Agent CLI, I want to run `env -u VIRTUAL_ENV uv run agent --version` and receive a correct, semantic version string (e.g., `v1.2.0` or `v1.2.0-4-g9a2b`), regardless of whether I am running from source or an installed package, so that I can report bugs and verify installations accurately.

## Acceptance Criteria
- [ ] **Scenario 1: Dev Mode**: Given I am in a git repository, When I run `env -u VIRTUAL_ENV uv run agent --version`, Then it outputs the result of `git describe --tags --always --dirty` (e.g., `v1.0.0-4-gHASH`).
- [ ] **Scenario 2: Distribution Mode**: Given I am running from a packaged build (no `.git` dir), When I run `env -u VIRTUAL_ENV uv run agent --version`, Then it outputs the version stamped in the `VERSION` file.
- [ ] **Scenario 3: Build Process**: The `package.sh` script MUST generate a `VERSION` file containing the current git description before creating the archive.
- [ ] **Scenario 4: Fallback**: If neither `.git` nor `VERSION` file exists, it falls back to a safe default (e.g., `unknown` or `v0.0.0`).

## Non-Functional Requirements
- **Performance**: Version check should be near-instant.
- **Reliability**: Must not crash CLI if version info is missing.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched:
- `.agent/src/agent/main.py`: CLI entrypoint.
- `package.sh`: Build script.
Workflows affected:
- Release process.

## Test Strategy
- Unit test for `main.py` version callback mocking file existence.
- Integration test running `package.sh` and verifying the artifact.

## Rollback Plan
- Revert changes to `main.py` and `package.sh`.
