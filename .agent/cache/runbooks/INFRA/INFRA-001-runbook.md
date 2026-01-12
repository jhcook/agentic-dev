```markdown
# INFRA-001: Smart AI Router and Python Rewrite

Status: PROPOSED

## Goal Description
The primary goal is to enhance the existing agent architecture by implementing a Smart AI Router capable of dynamically selecting the best AI model based on specific criteria (e.g., tier, context window). Additionally, core components of the agent will be rewritten in Python to improve maintainability and transparency. 

The implementation of the Smart AI Router ensures optimization of operational costs and AI model performance. Furthermore, this work includes replacing legacy dependencies with `google-genai` SDK and `tiktoken` libraries for modern compatibility and functionality. 

Key changes also include updating legacy tests to align with the improved implementation, ensuring passing builds with continuous integration.

## Panel Review Findings

### **@Architect**
- There is no mention of an ADR for the changes being introduced. As per governance rule `adr-standards.mdc`, a new ADR must be created and approved for both the SmartRouter design decision and the architectural implications of the Python rewrite.
- The description mentions replacing `agent/core/ai.py`. This should be reflected as a boundary change in the architecture diagram.
- The decoupling provided by the SmartRouter design must ensure scalability and future extensibility and adhere to microservice or modular design principles.

### **@Qa**
- The story lists unit tests for SmartRouter, integration tests for `agent preflight`, and verification of the legacy test suite. However:
  - There is no mention of creating performance tests to verify the 10ms decision time.
  - Specific test cases for failure scenarios and fallbacks (e.g., when an AI provider fails) must be added for robust validation.
  - Legacy test coverage may need enhancements for new APIs or business logic changes.

### **@Security**
- No security implications or requirements specific to the new dependencies (`google-genai`, `tiktoken`) have been mentioned. Their configurations, credential handling, and permissions need auditing to align with the project’s security policies.
- Any new integration points with external systems (e.g., APIs from `google-genai`) need to be compliant with organizational policies for handling third-party services.
- Ensure that no PII is shared through logs or external API calls (e.g., payloads sent to AI models).
- The Python rewrite should avoid accidental exposure or embedding of credentials or secrets. Leverage environment variables for secret management.
- Confirm that the failover mechanism does not compromise sensitive data when routing requests to alternative providers.

### **@Product**
- The acceptance criteria are well-defined and include both functional (SmartRouter logic and TokenManager) and non-functional (performance, reliability) requirements.
- The story does not clearly explain different operational scenarios for model transitions (e.g., low-tier vs high-tier model selection, context window conditions).
- Include a clear user-flow with examples of the SmartRouter decision process (e.g., given inputs, what output is expected).

### **@Observability**
- OpenTelemetry should be implemented to trace end-to-end processing via the SmartRouter, with attributes like `model_selected`, `decision_latency`, and `fallback_occurred` added as trace metadata.
- Structured logs should be added for all key events, including model selection, token usage, and fallback trigger.
- Add performance monitoring metrics, such as SmartRouter decision latency (to check for adherence to the 10ms requirement) and fallback success rates.

### **@Docs**
- A new ADR needs to be written and linked for SmartRouter design, including the rationale for adopting `google-genai` and `tiktoken`.
- Update `README.md` with explanations about the SmartRouter, its configuration, and new dependencies (`google-genai` and `tiktoken`).
- CLI help text for `agent preflight` and other relevant commands must be updated to explain how the router operates.
- Add a section to the CHANGELOG to document this change.

### **@Compliance**
- Confirm that no PII is captured or sent in API payloads in adherence to GDPR.
- Ensure compliance documentation is updated for new or modified third-party dependencies (`google-genai`, `tiktoken`).
- Verify that the rewritten Python modules continue to meet SOC2 requirements for data security and availability.

### **@Mobile**
- The story does not reference mobile functionality or compatibility, so no changes may be necessary. Confirm that any new APIs used by the app are well-documented and versioned properly to ensure API stability for mobile clients.

### **@Web**
- The story does not directly impact web features or Next.js-specific behavior. Verify whether any existing or new front-end features interact with the SmartRouter (e.g., if there is a UI component for configuring it).

### **@Backend**
- The use of `google-genai` SDK and `tiktoken` must be accompanied by rigorous integration testing. Ensure these dependencies are version-pinned in `pyproject.toml`. 
- Replace legacy code in `agent/core/ai.py` with clean, typed Python code. Ensure that all new libraries comply with Python type hints.
- The fallback mechanism to alternative AI providers must have robust checks and logging for why and when the fallback occurs.
- OpenAPI documentation must be updated according to `api-contract-validation.mdc`, and the OpenAPI specs must stay in sync. Use `python scripts/generate_openapi.py`.

## Implementation Steps

### SmartRouter Implementation
#### NEW `agent/core/smart_router.py`
- Implement `SmartRouter` class with the following features:
  - Decision logic for selecting the AI model.
  - Account for tier, context window, and fallback logic.
  - Dependency on `google-genai` and `tiktoken`.

#### MODIFY `agent/core/ai.py`
- Replace the current manual model selection logic with a call to `SmartRouter`.
- Remove the legacy dependency code.

### Python Rewrite
#### MODIFY [project-wide]
- Update existing Python scripts or modules with refactored Python code replacing legacy components. Follow Python typing conventions for all changes.

### Tests
#### NEW `tests/unit/test_smart_router.py`
- Add unit tests for all possible configurations of SmartRouter, including:
  - Different tier and context window configurations.
  - Fallback condition tests.

#### MODIFY `tests/legacy/`
- Update legacy tests for compatibility with the new Python implementation.

### CLI
#### MODIFY `agent/cli.py`
- Update CLI help text for `agent preflight` to document changes.

### OpenAPI
#### REGENERATE
- Update `docs/openapi.yaml` and compare against the previous version to ensure no breaking changes.

## Verification Plan

### Automated Tests
- [ ] Unit tests for `SmartRouter` pass with at least 90% coverage.
- [ ] Integration tests for `agent preflight` with SmartRouter functionality.
- [ ] Legacy tests updated and verified.
- [ ] Performance tests to validate <10ms decision latency.

### Manual Verification
- [ ] Manually test CLI to verify correct behavior of `agent preflight`.
- [ ] Manually verify fallback behavior with alternative AI providers.

## Definition of Done

### Documentation
- [ ] ADR created for SmartRouter and Python rewrite decisions.
- [ ] CHANGELOG.md updated to include changes.
- [ ] README.md updated with new CLI and SmartRouter details.
- [ ] API documentation updated to reflect new logic.

### Observability
- [ ] Structured logging implemented; no PII will be logged.
- [ ] OpenTelemetry tracing added to track request performance.
- [ ] Metrics implemented for decision latency and fallback success rate.

### Testing
- [ ] All unit tests pass with at least 90% coverage.
- [ ] All updated legacy tests pass.
- [ ] Integration tests for SmartRouter complete.
- [ ] Performance tests confirm router decision time <10ms.

### Compliance
- [ ] SOC2, GDPR, and other compliance requirements fulfilled.
- [ ] Dependency audit for `google-genai` and `tiktoken`.
```