# INFRA-007: Implement Agent Impact Command

## State
COMMITTED

## Problem Statement
The "Impact Analysis Summary" section in stories is critical for governance but often difficult to populate accurately manually. Developers may miss subtle dependencies or downstream effects of their changes. Automated analysis is needed to ensure this section is meaningful and accurate.

## User Story
As a Developer, I want to run `agent impact <story-id>` so that I can get an AI-generated analysis of how my changes affect the rest of the system, identifying potential risks, breaking changes, and affected workflows.

## Acceptance Criteria
- [ ] **Scenario 1**: Can run `agent impact <story-id>` with staged changes and receive a text analysis of the impact.
- [ ] **Scenario 2**: Can run `agent impact <story-id> --base main` to compare against a specific branch.
- [ ] **Scenario 3**: Can run with `--update-story` flag to automatically populate the "Impact Analysis Summary" section of the story markdown file.
- [ ] **Scenario 4**: The analysis correctly identifies basic risks (e.g., modifying a shared utility, changing a public CLI signature).
- [ ] **Scenario 5**: Fails gracefully if no changes are detected.

## Non-Functional Requirements
- **Performance**: Analysis should complete within reasonable time (AI latency driven).
- **Security**: Diff must be scrubbed of PII/Secrets before sending to AI (via `scrub_sensitive_data`).
- **Observability**: Logging of AI usage.

## Linked ADRs
- ADR-004: AI Governance Panel

### Impact Analysis of Code Changes

The proposed code changes introduce a new `impact` command to assist developers in analyzing the system-wide effects of their changes, leveraging both static analysis and AI-powered insights for governance purposes. The changes primarily touch command logic in `agent/commands/check.py` and introduce new functionality within a cleanly separated AI integration module (`agent/core/ai`).

---

## Impact Analysis Summary

**Components touched**:
- `agent/commands/check.py` (modified)
- `agent/core/ai/__init__.py` (new)
- `agent/core/ai/prompts.py` (new)
- `agent/core/ai/service.py` (new)

**Workflows affected**:
- Governance workflows: Introduces an automated system to populate the "Impact Analysis Summary."
- Development workflows: Adds tooling for impact-checking, especially beneficial for reviewing code changes and ensuring compliance with governance policies.

**Risks identified**:
1. **Security Risks**:
   - The AI integration requires sensitive code diffs and story content to be sent to external services such as OpenAI, Gemini, or GitHub's AI, increasing data exposure risk.
   - While the diff and story contents are scrubbed of PII/secrets (via `scrub_sensitive_data`), any flaws or gaps in this mechanism could expose private information.
2. **External Dependency Risks**:
   - The functionality relies heavily on external AI APIs, which may introduce downtime, latency, or rate-limiting issues.
   - The fallback logic for handling multiple AI providers (GitHub, Gemini, OpenAI) helps mitigate the impact of a single failure but does not eliminate reliance on external APIs.
3. **Error Management**:
   - Limited retry logic for handling API rate limits or transient failures (e.g., for the GitHub CLI). These retries are capped at three attempts, which could lead to partial or inconsistent results for users.
4. **Performance Risk**:
   - The AI-based analysis could be slow, especially for large diffs or congested API endpoints. This could deteriorate the developer experience if the latency becomes significant.

**Breaking Changes**:
No breaking changes were identified:
- The additions are backward-compatible with existing CLI commands and configurations.
- No existing APIs, database schemas, or workflows are altered.

---

### Detailed Analysis

#### Breaking Changes
The new functionality introduces an independent CLI command (`impact`) and new modules for AI integration. These changes are designed to be entirely additive and do not make modifications to existing commands or APIs. Therefore, no breaking changes are present.

#### Affected Components
1. `agent/commands/check.py`:
   - Added the `impact` function that implements the new CLI command.
   - Integrated AI-specific functionality (e.g., calling `scrub_sensitive_data` and generating/using AI prompts).

2. `agent/core/ai/` (new namespace created):
   - `prompts.py`: Contains a single function for generating a standardized AI analysis prompt.
   - `service.py`: Provides an abstraction layer for different AI provider implementations (GitHub CLI, Gemini, OpenAI), including provider fallback, error handling, and security scrubbing.
   - `__init__.py`: Exposes the `ai_service` module globally.

3. System commands:
   - New `impact` command allows AI-based and static analysis of changes via Git diff.

#### New Dependencies and Modules
1. **Rich Console**: Used for printing user-friendly messaging to the CLI. Library appears to already be in use, so no new dependency is introduced here.
2. **AI APIs**:
   - **GitHub CLI (gh)**: Ensures compatible installation.
   - **Gemini AI**: Checks for `GOOGLE_GEMINI_API_KEY`.
   - **OpenAI API**: Checks for `OPENAI_API_KEY`.
3. **New AI Logic**:
   - Fallback provider handling and environment variable checks ensure a priority hierarchy for the available providers (GH > Gemini > OpenAI).

#### Security Considerations
1. The `scrub_sensitive_data` method is invoked to clean diff and story content before sending it to external AI services. Its effectiveness is critical for protecting sensitive information. However, the implementation of `scrub_sensitive_data` has not been provided in the diff, and its thoroughness should be evaluated.
2. AI calls involve vendor APIs, and the system warns users to avoid including PII. However, robust user education and consistent audits of AI usage logs (as indicated by the observability requirement) are essential.

#### Observability
- AI service usage and latency are being logged, which is a necessary step for both performance monitoring and auditing purposes.
- The `impact` command appropriately handles user feedback through CLI messages (`rich.console`) for different scenarios, such as missing staged changes or unavailability of AI providers.

---

## Recommendations
1. **Validation of Scrubbing Logic**:
   - To mitigate security risks, an additional unit test suite should be implemented for `scrub_sensitive_data` to verify it effectively redacts sensitive content under various scenarios.
2. **AI Provider Reliability**:
   - While fallback mechanisms among the three AI providers are effective, consider enabling a local static fallback for generating basic impact analyses if all providers fail.
3. **Performance Metrics**:
   - Gather telemetry, such as average AI response latency, to identify bottlenecks and improve the developer experience.
4. **User Guidance**:
   - Given the reliance on sensitive context (e.g., code diffs), provide explicit documentation or warnings about what data should and shouldn’t be included.
5. **Additional Tests**:
   - Ensure exhaustive tests for the newly added integration with all AI providers, including error cases for rate limits, API failures, and malformed responses.

This feature appears well-designed and likely to improve release/deployment governance significantly by automating critical impact analysis steps. However, aligning all security and performance safeguards explicitly is critical due to its reliance on external, opaque AI systems.
## Test Strategy
- Unit tests for the `impact` command logic.
- Mock the AI service to verify prompt construction and response handling.
- Integration test ensuring the file update mechanism works.

## Rollback Plan
- Revert the changes to `agent/commands/check.py`.
