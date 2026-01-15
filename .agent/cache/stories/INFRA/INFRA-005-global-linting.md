# STORY-INFRA-005: Global and Path-Based Linting

## State
COMMITTED

## Problem Statement
The current `agent lint` command is hardcoded to specific internal directories (`.agent/src`, `.agent/bin`) and specific languages (Python, Shell). This prevents it from being used as a universal linting tool for the entire repository, especially as we add new components like web frontends or backend services in different directories and languages.

## User Story
As a developer, I want `agent lint` to be able to scan any directory or the entire repository and support multiple languages, so that I have a consistent single interface for verifying code quality across the project.

## Acceptance Criteria
- [ ] **Path Argument**: `agent lint <path>` scans the specified directory or file, respecting relative paths from CWD.
- [ ] **Global Flag**: `agent lint --all` scans recursively from the current working directory (respecting .gitignore).
- [ ] **Default Behavior**: `agent lint` (no args) continues to scan only staged files.
- [ ] **Base Config**: `agent lint --base <branch>` scans changes relative to the base branch.
- [ ] **Language Support**: Automatically detects and lints `*.py` (ruff) and `*.sh` (shellcheck) files in the target set.
- [ ] **Web Support (Future-proofing)**: The architecture supports adding `*.ts`/`*.js` easily.
- [ ] **Negative Test**: Running on a path with no supported files returns a clean/empty result gracefully.

## Non-Functional Requirements
- **Performance**: Scanning the full repo should be reasonably fast (use batching).
- **Usability**: The CLI should provide clear feedback on which files are being linted.
- **Compatibility**: Must work on macOS, Linux, and Windows (dev environment) and CI.

## Linked ADRs
- N/A

## Impact Analysis Summary
- **Components touched**: `.agent/src/agent/commands/lint.py`
- **Workflows affected**: `agent lint` usage; `preflight` workflow (if it uses `lint --all` in the future).
- **Risks identified**: Potential performance regression if not batched correctly; external dependencies (npm) might be missing in some environments.

## Test Strategy
- **Unit Tests**: Test `get_files_to_lint` logic with various path/arg combinations.
- **Manual Verification**:
    - Run `agent lint --all` and verify it catches issues in the current working directory.
    - Run `agent lint .` (root) and verify it works.
    - Run `agent lint non-existent/` and verify error handling.
    - Run `agent lint --all non-existent/` and verify error handling.
    - Run `agent lint --all web/` and verify it lints all files in the web directory.
    - Run `agent lint` and verify it lints staged git files.
    - Run `agent lint --base main` and verify it lints all changes relative to the base of main.

## Rollback Plan
- Revert the changes to `lint.py` to restore the hardcoded paths.
