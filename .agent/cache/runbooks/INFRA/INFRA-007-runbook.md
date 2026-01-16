# INFRA-007: Implement Agent Impact Command

Status: ACCEPTED

## Goal Description
Enable developers to identify system impact and risks associated with their code changes through an automated command `agent impact <story-id>`.

This command will generate an AI-driven impact analysis report based on a comparison of the staged changes or against a specific branch (via `--base` flag). As an optional enhancement, the command can also update the "Impact Analysis Summary" section of the corresponding story markdown document directly.

## Panel Review Findings

- **@Architect**:  
  The design introduces a meaningful addition to the development process, helping enforce governance requirements. However, clear modularization is needed for future extensibility and maintainability. Ensure that the command integrates smoothly into existing tooling using well-structured APIs.

- **@Security**:  
  The use of AI introduces potential security implications, especially if sensitive or proprietary data is inadvertently included in prompts sent to external services. Rigorous use of the `scrub_sensitive_data` function and logging to AI requests must be enforced. Sensitive parts of the analysis, such as API keys or private configurations, must be excluded.

- **@QA**:  
  The testing scope is adequate, but ensuring high-quality mock data for AI responses is critical. Validation of not only correct functionality but also graceful handling of failures (e.g., timeout, empty diff) must be part of the QA process. Testing `--update-story` operations must include edge cases for malformed markdown files.

- **@Docs**:  
  Clear documentation on the usage of the `agent impact` command is crucial, including all flags and expected output. Potential updates to developer guidelines for generating consistent impact analysis summaries are also suggested for long-term consistency.

- **@Compliance**:  
  All new logic impacting governance, such as the auto-update functionality for markdown files, must conform to standardized review practices. Additionally, ensure that the logs of AI analysis requests are structured for auditability while excluding sensitive details.

- **@Observability**:  
  Observability concerns are adequately addressed if explicit metrics for AI usage and latency are implemented. This enhances monitoring for abnormal delays or spikes in usage. Logs must be anonymized and human-readable.

## Implementation Steps

### Agent CLI Command Infrastructure
#### [MODIFY] `agent/commands/check.py`
- Add a new subcommand `impact` to the CLI structure using the `argparse` library framework.
- Define the following flags:
  - `<story-id>`: Required input parameter.
  - `--base`: Optional flag for specifying a branch to compare against.
  - `--update-story`: Optional flag to update the markdown story file directly.
- Integrate subprocess call to fetch staged changes or diff with specified branch.

---

### AI Prompt Generation
#### [NEW] `agent/core/ai/prompts.py`
- Develop a reusable function `generate_impact_prompt(diff: str, metadata: dict) -> str` to structure prompts for the AI model.
- Sanitization: Call the pre-existing `scrub_sensitive_data` function on all diff data.
- AI Response Handling: Parse the AI response into Markdown-compatible text.

---

### Write Output to Story Files
#### [MODIFY] `agent/commands/check.py`
- Create helper function `update_story_file(story_id: str, analysis: str)`:
  - Validate the file exists and follows correct structure.
  - Parse the file to locate "Impact Analysis Summary".
  - Inject the newly generated summary.

---

### Logging and Observability
#### [MODIFY] `agent/commands/check.py`
- Implement logging for each major operation:
  - Time taken to generate the diff.
  - Time taken for AI analysis (round-trip latency).
  - AI request success/failure (with status).

#### [NEW] `agent/core/logging/impact.py`
- Add a dedicated logger for the `impact` command. Ensure logging levels are aligned with existing governance (e.g., warn only on scrubbed sensitive data).

---

## Verification Plan

### Automated Tests

- [ ] Test that `agent impact <story-id>` correctly detects changes and returns an impact analysis string.
- [ ] Test `--base` functionality for branch-to-branch diffing.
- [ ] Test `--update-story` on a valid markdown file to ensure the "Impact Analysis Summary" section updates correctly without corrupting the rest of the file.
- [ ] Test that no sensitive data from the code changes or metadata is included in the AI request payload.
- [ ] Test for scenarios where there are no changes, invalid command inputs, or failure connecting to the AI service.

### Manual Verification

- [ ] Validate example outputs of the `agent impact` command on realistic diffs with the observed system.
- [ ] Verify behavior when the AI service is unavailable (e.g., HTTP 503 failures).
- [ ] Compare generated impact content directly with staged changes for accuracy.

## Definition of Done
### Documentation
- [ ] `CHANGELOG.md` updated with details of the new functionality.
- [ ] `README.md` updated with an additional section for the `agent impact` command, specifying usage and flags.
- [ ] Internal developer documentation updated for guidelines on crafting high-quality impact analysis.

### Observability
- [ ] Add AI usage metrics: counts of requests, success/failure rates, latency.
- [ ] Ensure all logs exclude sensitive data.

### Testing
- [ ] All new unit tests pass.
- [ ] Integration tests for file writing and diff comparison pass.
- [ ] Demonstrate compliance with security validations (e.g., sensitive data scrubbing).