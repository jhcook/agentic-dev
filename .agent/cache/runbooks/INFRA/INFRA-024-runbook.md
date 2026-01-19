# INFRA-024: Agent List Models Command

## State
ACCEPTED

## Goal Description
To implement a command `agent list-models` in the CLI tool, which queries and displays available AI models for a specified provider. These models should be filtered based on the user's active API key, provider configuration, and the availability status of the models. The goal is to enhance developer productivity by providing real-time visibility into available models and avoiding runtime API call errors (e.g., "404 Model Not Found").

## Panel Review Findings

- **@Architect**:  
The solution aligns well with modularity and separation of concerns. Fetching models via a specific provider's API method ensures scalability for additional providers in the future. Dependency on the `client.models.list()` API is acceptable, but we recommend clearly abstracting this API call into a dedicated service layer (e.g., `agent/core/ai/service.py`) to ensure maintainability.

- **@Security**:  
No security issues identified in the provided user story. However, attention must be given to the following:
  1. Ensure that logging or error messages do not inadvertently leak API keys.
  2. Implement rate limiting or provide user warnings if API load spikes due to repetitive use.
  3. Validate provider arguments and API keys to prevent injection attacks.

- **@QA**:  
This feature introduces multiple scenarios, including positive and negative test cases, which must be comprehensively covered. Focus should be on simulating failure modes (e.g., invalid API key, unreachable provider). Additionally, output formatting must be validated for usability and consistency across providers.

- **@Docs**:  
The CLI command requires detailed documentation, including:
  1. A clear example usage of all possible arguments.
  2. Response format description (e.g., table format, fields listed).
  3. Instructions for troubleshooting (common errors, their causes, and fixes).
  Align documentation efforts with developer experience guidelines.

- **@Compliance**:  
The proposed CLI command does not appear to violate any governance rules. However:
  1. The ADR standards rule requires linking any new development to its rationale through an ADR. There is currently no existing ADR linked to this feature justification. A proper ADR should be introduced and explicitly linked before merge.
  2. API modifications should be assessed against the `api-contract-validation.mdc`. Validation scripts must execute as part of CI/CD pipelines to confirm no breaking changes occur.

- **@Observability**:  
Observability planning is needed:
  1. Logs should capture details, such as the provider selected, the API endpoint invoked, and any errors encountered.
  2. Metrics should be registered for monitoring usage, processing time, and any API failures across providers.
  3. Logs must avoid inclusion of sensitive information such as API keys or tokens.

---

## Implementation Steps

### agent CLI Command
#### MODIFY `agent/commands/list.py`
- Add a new `list_models` function for `list-models` subcommand.
- Follow existing pattern from `list_stories`, `list_plans`, `list_runbooks` functions.

#### NEW `agent/commands/models.py`
- Create a dedicated module for model listing commands.
- Implement function `list_models(provider: str)`:
  - *Input Validation*: Check that `provider` is valid and configured.
  - If `provider` is missing, use the active/default provider.
  - Call the respective `client.models.list()` API for the provider. For `gh`, invoke the GitHub CLI with appropriate arguments.
  - Parse and format the response into a readable table or list format (e.g., `tabulate` package).
  - Handle error scenarios and display actionable messages.

#### NEW Unit Test File `tests/test_list_models.py`
- Add unit tests to cover:
  - Scenarios with valid providers (`gemini`, `openai`, `anthropic`, `gh`).
  - Error scenarios, such as invalid provider or missing API key.
  - Default provider when no argument is given.
- Follow existing test patterns from `tests/test_ai_service.py`.

### AI Service Integration
#### MODIFY `agent/core/ai/service.py`
- Add a new helper method `get_available_models(provider: str) -> List[str]` to encapsulate logic for selecting provider-specific API calls (`client.models.list()`).

### Error and Logging
#### MODIFY `agent/utils/logging.py`
- Implement structured logging for the new command. Include fields for:
  - Action (`list-models`).
  - Provider.
  - Errors (if any).
- Mask any sensitive user information (e.g., API tokens).

---

## Verification Plan

### Automated Tests
- [ ] Test `agent list-models` with valid providers; verify output for each provider matches the mocked API responses.
- [ ] Test with invalid providers to ensure errors are handled gracefully.
- [ ] Test scenario where API keys are missing or invalid (negative test case).
- [ ] Check command response time for acceptable performance under network latency simulations.

### Manual Verification
- [ ] Run `agent list-models` locally with all provider options (`gemini`, `openai`, `gh`, no args/default) and compare outputs against real-world API/CLI responses.
- [ ] Test logging behavior to ensure sensitive information is not leaked.
- [ ] Verify error messages are informative and actionable for the end user.

---

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated to describe the feature addition.
- [ ] README.md updated to include instructions for `agent list-models`.  
- [ ] CLI usage examples added to the documentation with provider-specific use cases.

### Observability
- [ ] Logs are captured for key command metrics, with sensitive data removed.
- [ ] Metrics are reported for API latency and command usage frequency.

### Testing
- [ ] Unit test coverage >90% for new code paths.
- [ ] Integration test runs without errors when provider credentials are valid and available.

### Compliance
- [ ] New feature is linked to an approved ADR to comply with governance rules.
- [ ] Governed CI rules for API contract validation run successfully, confirming no breaking changes.