# INFRA-007: Implement Agent Impact Command

## State
COMMITTED

## Problem Statement
The "Impact Analysis Summary" section in stories is critical for governance but often difficult to populate accurately manually. Developers may miss subtle dependencies or downstream effects of their changes. Automated analysis is needed to ensure this section is meaningful and accurate.

## User Story
As a Developer, I want to run `env -u VIRTUAL_ENV uv run agent impact <story-id>` so that I can get an AI-generated analysis of how my changes affect the rest of the system, identifying potential risks, breaking changes, and affected workflows.

## Acceptance Criteria
- [ ] **Scenario 1**: Can run `env -u VIRTUAL_ENV uv run agent impact <story-id>` with staged changes and receive a text analysis of the impact.
- [ ] **Scenario 2**: Can run `env -u VIRTUAL_ENV uv run agent impact <story-id> --base main` to compare against a specific branch.
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

```markdown
## Impact Analysis Summary

**Components touched**:
- `agent/commands/check.py` (modified)
- `agent/core/ai/__init__.py` (new)
- `agent/core/ai/prompts.py` (new)
- `agent/core/ai/service.py` (new)
- `.agent/workflows/impact.md` (new)

**Workflows affected**:
- **Governance workflows**: Automates the "Impact Analysis Summary" section of Story files, improving compliance and reducing manual effort for developers.
- **Development workflows**: Adds a new tool (`env -u VIRTUAL_ENV uv run agent impact`) for analyzing and reviewing changes, especially for identifying risks and downstream dependencies.

**Risks identified**:
1. **Security Risks**:
   - Code diffs and Story content are sent to external AI services, introducing potential data leakage risks. The effectiveness of `scrub_sensitive_data` is critical and requires thorough validation.
2. **Dependency Risks**:
   - Relies heavily on external AI APIs (GitHub CLI, Gemini, OpenAI). Failures, rate limits, or downtime from these providers could reduce reliability.
3. **Performance Risks**:
   - AI-based analysis might experience latency on large diffs or under congested conditions. Monitoring and optimization for these cases are recommended.
4. **Error Handling**:
   - Limited retry mechanisms for transient API failures may lead to incomplete or inconsistent results during provider issues.

**Breaking Changes**: No  
- The changes are entirely additive, introducing a new CLI command and cleanly separated AI modules. Existing commands, APIs, or workflows remain unaffected.

---
```
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
