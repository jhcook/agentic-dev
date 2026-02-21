# STORY-ID: INFRA-042: Implement Interactive Preflight Repair

## State

ACCEPTED

## Goal Description

Develop an interactive "fix" mode for the `env -u VIRTUAL_ENV uv run agent preflight` command to help developers resolve errors more efficiently. When preflight checks fail, the tool will identify blockers, propose specific AI-generated fixes, allow developers to apply and verify fixes in real-time, and ensure human oversight before any automated changes are finalized.

## Panel Review Findings

- **@Architect**:
  - The proposed architecture is well thought out, especially the segregation of `InteractiveFixer` into `agent.core.fixer` as a loosely coupled module.
  - The flow from issue detection → fix proposal → verification → rollback is clear and adheres to principles of modularity and maintainability.
  - Recommendation: Ensure extensibility for adding new failure types for analysis and repairs in the future.

- **@Security**:
  - Introducing AI-generated code changes can lead to exploitation if not sandboxed or validated. Ensure AI service outputs are run through rigorous schema and content validation before being presented to the user.
  - Recommendation: Use secure configurations when presenting diffs and integrate warnings for sensitive data exposure.
  - Risk Mitigation: Add test cases to identify and mitigate malicious outputs from the AI, and ensure `git stash` guarantees buffer integrity.

- **@QA**:
  - The comprehensive failure analysis and retries are well outlined; however, edge scenarios (e.g., improperly formatted diffs, partial failures) should be tested thoroughly.
  - Recommendation: Simulate high-stress scenarios (e.g., failed fixes cascading through multiple layers) to ensure resilience.
  - Must clarify expected behaviors when AI proposals fail verification.

- **@Docs**:
  - Documentation requirements are clear in terms of enhancing CLI usage documentation and changelogs.
  - Recommendation: Add an appendix or example use cases (CLI outputs/screenshots of interactive mode) to the README to help developers onboard.
  - Ensure all new features are backward-compatible by documenting their optional nature.

- **@Compliance**:
  - The feature must comply with ADR standards. Ensure all architectural details (e.g., decisions on `agent.core.fixer` and AI selection) are recorded under an ADR before merging.
  - Clarify linkage between this implementation and any existing ADRs or governance processes.
  - Ensure all commits are tied to their documented ADRs with evidence of alignment.

- **@Observability**:
  - Telemetry should be added for fix generation, edits applied, and retries. These can help monitor both expected failures and real-world usage.
  - Recommendation: Add metrics such as “success rate of first fix” and “average time between resolution and identification.”
  - Logs should clearly segregate user inputs, AI outputs, and any sensitive files. Avoid including PII or sensitive data.

## Implementation Steps

### agent/commands/check.py

#### [MODIFY] Implement `--interactive` flag

- Extend the `preflight` command to include a new `--interactive` flag.
- Route the flag to trigger `agent.core.fixer` logic for interactive fixes.

### agent/core/fixer.py

#### [NEW] Create `InteractiveFixer` module

- Implement the `InteractiveFixer` class, housing the main entry point for preflight error analysis and resolution.
  - `def analyze_failures(failure_log: str) -> List[Failure]:`
    - Parse raw preflight failure logs.
    - Categorize failures (Story schema, linting, or unit tests) into specific actionable items.
  - `def generate_proposals(failure: Failure) -> List[Proposal]:`
    - Use `agent.core.ai` to create structured AI-generated fix proposals.
    - Validate against potential schema mismatches or unsafe content.

- Implement the verification loop:
  - Apply the user-selected fix.
  - Re-run the specific preflight check using `subprocess.run()`.
  - If fixed, mark as resolved. If not, offer retry or revert.
- **Safety**: Implement `git stash` before applying patches and `git stash pop` on revert/exit to ensure workspace integrity.

### agent/core/ai/fix_utils.py

#### [NEW] Integrate AI proposal generation

- Extend the AI service module to analyze failures and propose fixes:
  - Input: Failure metadata (Type, root cause).
  - Output: JSON-structured file diff or patch proposals.

### agent/core/utils.py

#### [MODIFY] Add utilities for applying/validating diffs

- Create utility functions for:
  - Generating a "diff preview" between the current and proposed state.
  - Reverting failed fixes via "git reset --hard HEAD~1" or `git stash pop`.

### docs/command_reference.md

#### [MODIFY] Document new `env -u VIRTUAL_ENV uv run agent preflight --interactive` flag

- Provide detailed usage examples, including a walkthrough of an interactive repair scenario.

### Tests

#### Unit Testing in `agent/tests/unit/test_fixer.py`

- [ ] Validate `analyze_failures()` produces correct failure classification.
- [ ] Mock `generate_proposals()` and test fix application logic.
- [ ] Ensure fixes do not proceed without user confirmation.

#### Integration Testing in `agent/tests/integration/test_preflight_interactive.py`

- [ ] Simulate a corrupted Story schema and verify fix flow works end to end.
- [ ] Simulate edge cases: failed fixes, manual reverts.
- [ ] Validate all logs for readability and compliance (e.g., no PII is leaked).

## Verification Plan

### Automated Tests

- [ ] Unit tests for each function in `InteractiveFixer`.
- [ ] Integration test for the full repair and verification flow.

### Manual Verification

- [ ] Corrupt a story file, use `env -u VIRTUAL_ENV uv run agent preflight --interactive`, and verify both the fix proposal and final result.
- [ ] Test linter and unit test errors and validate fixes.
- [ ] Confirm rollback integrity after failed fixes.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated to log release details.
- [ ] README.md updated with CLI documentation and examples.
- [ ] ADR for `InteractiveFixer` created and approved.

### Observability

- [ ] Add logs for fix generation, execution, and user actions (suppress sensitive outputs).
- [ ] Add metrics for fix success and generator efficiency.

### Testing

- [ ] Unit tests passed for all new modules.
- [ ] Integration tests confirm end-to-end functionality for preflight repair scenarios.
