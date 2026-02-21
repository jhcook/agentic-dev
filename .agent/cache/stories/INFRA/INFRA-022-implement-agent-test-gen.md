# INFRA-022: Implement Agent Test Gen

## State
COMMITTED

## Problem Statement
We have legacy code or new prototypes that lack unit test coverage. Writing boilerplate tests (setup, mocks, assertions) is tedious and often skipped. "Zero coverage" areas become "Fear Zones" that developers avoid refactoring.

## User Story
As a Developer, I want to run `env -u VIRTUAL_ENV uv run agent test-gen <source_file>` to automatically generate a comprehensive `pytest` file with mocked dependencies, so that I can quickly establish a safety net for my code.

## Acceptance Criteria
- [ ] **Targeting**: Accepts a python source file path.
- [ ] **Safety**: Check if a test file already exists. If yes, generate `test_<filename>_gen.py` or ask to append, to avoid overwriting manual work.
- [ ] **Mocking**: Automatically identifies external dependencies (database calls, API requests) and generates `unittest.mock.MagicMock` fixtures. **Mocks must be explicit** to avoid side effects.
- [ ] **Style**: Generates functional `pytest` style tests (fixtures + assert), NOT `unittest.TestCase` classes.
- [ ] **Auto-Refinement**: Runs the generated test immediately. If it fails (syntax or logic error), feeds the error back to the LLM to fix it (up to 3 retries).
- [ ] **Reporting**: Reports the test execution result and, if available, the `pytest-cov` coverage increase for the target file.

## Non-Functional Requirements
- **Isolation**: Generated tests must NOT perform actual I/O.
- **Security**: Mocks must NEVER hardcode real secrets or API keys; use `os.environ` or dummy values.
- **Resilience**: The refinement loop must utilize a strict token limit to avoid infinite loops.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/test_gen.py` (new), `agent/core/ai/testing.py` (new).
Workflows affected: Testing / QA.
Risks identified: "Mock hallucination" (mocking methods that don't exist).

## Test Strategy
- **Unit Tests**:
    - Pass a simple Calculator class to the generator and assert it produces `test_calculator.py` with valid mocks.
- **Integration Tests**:
    - Run on a known "messy" file in the repo and verify the generated test passes.

## Rollback Plan
- Delete the command file.

