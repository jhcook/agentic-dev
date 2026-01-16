# STORY-ID: INFRA-009: Implement UI Tests Runner

Status: ACCEPTED

## Goal Description
The objective is to enable developers to execute UI tests using the `agent` CLI tool with the `run-ui-tests` command. This implementation will integrate the Maestro CLI to execute `.yaml` test flows, ensuring compatibility with the intended automation framework.

## Panel Review Findings

- **@Architect**:
  - Approves the selection of Maestro as it supports both mobile and web platforms, aligning with potential future scalability.
  - Concern: No mention of error handling for unsupported test flow files or improper directory structure; this must be explicitly designed.
  - Suggestion: Factor in configurability for the directories to allow flexibility for repositories with different structures.

- **@Security**:
  - Concern noted that the `maestro` CLI's capability to execute external scripts could open avenues for unwanted execution of malicious code. Implement validation for the `.yaml` flows.
  - Ensure errors and logs do not output sensitive information.
  - Validation is needed for CLI arguments to avoid command injection vulnerabilities.

- **@QA**:
  - Tests will need to cover all specified acceptance criteria.
  - Consider edge cases, e.g., missing Maestro CLI, empty `.yaml` files, incorrect syntax in test flows.
  - Suggest mocking `maestro` executions during testing to ensure the feature functions even when `maestro` is not available during unit tests.

- **@Docs**:
  - The README should include comprehensive examples of how to use the `run-ui-tests` command, sample `.yaml` structure for flows, and troubleshooting steps if `maestro` is missing or an error occurs.
  - Include inline code comments explaining the functionality for maintainability.

- **@Compliance**:
  - Although not impacting the API, the implementation needs to adhere to governance rules. Documentation about how debug logs will manage PII must be included.
  - Logic changes should be tracked in the Implementation Plan `INFRA-008`.

- **@Observability**:
  - Ensure the command execution is properly logged for observability purposes (i.e., when it is run, directory scanned, file executed, and exit codes).
  - Error logging must be verbose enough to debug, but sanitized to prevent PII leakage.
  - Consider monitoring metrics, such as execution time per test suite, number of tests executed, and success/failure rates.

## Implementation Steps

### agent CLI
#### [MODIFY] `agent/commands/check.py`
1. Define a new `run_ui_tests` command method within the `commands` class.
2. Validate that the `maestro` CLI is available on the system path:
   - Use `shutil.which("maestro")`.
   - If not found, output `error: Maestro CLI is not installed. Please install it.` and return an error exit code (e.g., 1).
3. Identify UI test flow files:
   - Default directories to check: `tests/ui/` and `.maestro/`.
   - Retrieve all `.yaml` files in a recursive directory scan.
   - If no `.yaml` files are found, exit with a message like `info: No test flows found` and an exit code of 0.
4. Run each flow using the `maestro test <flow.yaml>` command:
   - Provide logs indicating the start and end of execution for each flow.
   - Capture `maestro`'s exit code.
   - Consolidate results:
     - Exit with a non-zero exit code if any flow test fails.
     - Otherwise, exit with 0.
5. Add an optional argument to filter `.yaml` files by a substring match using `argparse.ArgumentParser` (e.g., `agent run-ui-tests --filter <keyword>`).

### Error Handling
1. User-friendly error messages for:
   - Missing Maestro CLI.
   - Missing/No `.yaml` files in target directories.
   - Invalid YAML syntax (use `yaml.safe_load` with exception handling).
   - Unexpected errors during execution.
2. Logs should be written to `.agent/logs/agent_run_ui_tests.log`.
3. Provide contextual information in error logs for debugging.

### Tests
#### [NEW] `tests/test_agent_run_ui_tests.py`
1. Include unit tests for the `run_ui_tests` functionality:
   - Mock `shutil.which` to simulate scenarios where `maestro` is/ is not installed.
   - Mock the directory scanning, `.yaml` availability, and syntax correctness.
   - Mock `subprocess.run` for `maestro test` to avoid actual Maestro execution during tests.
2. Example Test cases:
   - Valid flow execution.
   - Directory structure with no `.yaml` files.
   - CLI argument validations (e.g., invalid filter patterns).
   - Maestro missing (error scenario).
   - Simulated invalid YAML syntax (should gracefully handle).

### Documentation
#### [MODIFY] `README.md`
1. Update the README to include usage examples for `agent run-ui-tests`.
   - Example with default behavior.
   - Example with `--filter` argument.
2. Describe sample `.yaml` test flow format and naming conventions.
3. Add a Troubleshooting section:
   - Missing Maestro CLI.
   - Empty test directories.
   - Invalid `.yaml` syntax.

#### [MODIFY] `.agent/adrs/INFRA-008.md`
1. Add a `## Changes` section, and note the implementation details of INFRA-009.

### Logging & Observability
#### [NEW] Logging Configuration: `.agent/logs/agent_run_ui_tests.log`
1. Log:
   - Execution start/end timestamps.
   - Identified `.yaml` files.
   - Results of each Maestro test flow (e.g., pass, fail).
2. Sanitize logs to prevent sensitive information exposure.
3. Include metrics such as execution time and number of flows found.

## Verification Plan

### Automated Tests
- [ ] Add unit tests with mocks as per the cases mentioned.
- [ ] Full script execution simulation using test directories and dummy `.yaml` test flows.

### Manual Verification
- [ ] Install and test on machines with/without `maestro`.
- [ ] Use valid, empty, and malformed `.yaml` files in both standard and non-standard directories.
- [ ] Observe logs for proper data capture and sanitization.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated to include the new feature.
- [ ] README.md updated with usage instructions and troubleshooting.

### Observability
- [ ] New log file created: `.agent/logs/agent_run_ui_tests.log`.
- [ ] Error and transaction logs sanitized.
- [ ] Metrics added for `maestro test` execution (e.g., number of flows, pass rate).

### Testing
- [ ] Unit tests pass.
- [ ] Integration tests simulate full execution flow correctly.
- [ ] Manual tests confirm behavior on multiple environments.