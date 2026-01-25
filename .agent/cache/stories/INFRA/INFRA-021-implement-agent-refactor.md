# INFRA-021: Implement Agent Refactor

## State
INFRA-021-021-021-021-021-021-021-021-021-021-021-021-021-021-021-021-021-021

## Problem Statement
Refactoring code across multiple files (e.g., renaming a utility function used everywhere, or creating value objects) is tedious and error-prone. While IDEs handle simple renames, complex logical refactors (like "Extract this logic into a Strategy pattern") require understanding the semantic meaning of the code, which standard regex/tools cannot do.

## User Story
As a Developer, I want to run `agent refactor <file_or_dir> --goal "Goal"` to apply complex, AI-driven refactoring across a set of files, so that I can improve code quality and architecture without spending hours on manual edits.

## Acceptance Criteria
- [ ] **Target Selection**: The command accepts a file or directory path. For directories, it uses smart heuristics (grep/imports) to limit context, rather than dumping all files.
- [ ] **Goal-Driven**: The user provides a natural language goal (e.g. "Extract the validation logic in these files to a new Validator class").
- [ ] **Plan-First**: The agent first generates a "Refactoring Plan" which includes a **Diff Summary** of changes. The "Apply" prompt defaults to 'No' for safety.
- [ ] **Evaluation>: Automatically runs a syntax check (e.g. `ruff` or `python -m compileall`) immediately after edits.
- [ ] **Verification**: Defaults to running `pytest` (or a specific test target) post-refactor. If tests fail, it offers to revert changes.
- [ ] **Undo**: Provides an option (or suggests a git command) to easily undo the refactor if the user is unhappy with the result.

## Non-Functional Requirements
- **Safety**: The command requires the git working tree to be clean before running.
- **Security**: The AI prompt must explicitly instruct the model to preserve existing security logic (e.g. input (sanitization).
- **Accuracy**: Valid Python syntax is non-negotiable.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/refactor.py` (new), `agent/core/ai/coding.py` (new).
Workflows affected: Development.
Risks identified: AI breaking logic in subtle ways not caught by tests.

## Test Strategy
- **Unit Tests**:
    - Mock the LLM to return specific code changes and verify they are applied to files correctly.
- **Integration Tests**:
    - Create a temporary Python project, run a rename refactor, and verify valid syntax + passing tests.
    - Verify that simpler "syntax errors" triggers an auto-revert or warning.

## Rollback Plan
- Delete the command file.

