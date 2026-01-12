# Governance Preflight Report

Story: INFRA-005

### ✅ @Architect: PASS

### ❌ @Security: BLOCK
VERDICT: BLOCK

### Brief analysis of findings relative to your focus.

The implementation introduces necessary, robust security controls (PII scrubbing utility, environment variable secret management) but fails to apply these controls consistently across all new AI-driven workflows, creating a PII leak path.

#### 1. PII Leaks (BLOCK)
The core security risk lies in the commands that transfer internal documentation (Stories, Runbooks) to external LLM providers (Gemini, OpenAI).

*   **Positive Finding**: The utility function `agent.core.utils.scrub_sensitive_data` is implemented with regex patterns targeting emails, IPs, and common API key formats (fulfilling ADR-016 and GDPR/SOC 2 requirements). This is validated by tests (`test_scrubber.py`).
*   **Critical Gap**: The new AI commands (`plan`, `new-runbook`, `implement`, `match-story`) load sensitive context (Story or Runbook content) and pass it directly into the AI prompts in `plan.py`, `runbook.py`, `implement.py`, and `match.py`. Unlike the `preflight` command in `check.py` which correctly calls `scrub_sensitive_data` on the diff and story content, these other command implementations **do not** apply the scrubbing utility before transmission.

This omission directly violates the security commitment documented in ADR-016, which requires active sanitization on all content sent to third-party processors.

#### 2. Hardcoded Secrets (PASS)
The new `AIService` loads API keys exclusively from environment variables (`GOOGLE_GEMINI_API_KEY`, `OPENAI_API_KEY`). No hardcoded secrets were introduced in the diff.

#### 3. Injection Vulnerabilities / Permission Scope
The prompt generation logic handles content as unstructured text, reducing the risk of classic injection (RCE). However, the implementation of the `preflight` command relies on nine specialized AI agents reading the rules and providing feedback, which is a significant, complex prompt structure. The security mitigation relies heavily on the "Security" agent prompt definition, but the prerequisite security control (PII scrubbing) is the immediate concern.

---
### REQUIRED_CHANGES:

The `scrub_sensitive_data` utility must be imported and applied to all content variables (Story content, Runbook content, etc.) before they are used in the `ai_service.complete()` call for the following files:

1.  **`.agent/src/agent/commands/plan.py`**: Apply scrubbing to `story_content` and `rules_content` before constructing `user_prompt`.
2.  **`.agent/src/agent/commands/runbook.py`**: Apply scrubbing to `story_content` and `rules_content` before constructing `user_prompt`.
3.  **`.agent/src/agent/commands/implement.py`**: Apply scrubbing to `runbook_content`, `guide_content`, and `rules_content` before constructing `user_prompt`.
4.  **`.agent/src/agent/commands/match.py`**: Apply scrubbing to `files`, `stories_context`, and `rules_content` before constructing `user_prompt`.

### ✅ @Compliance: PASS

### ❌ @QA: BLOCK
**VERDICT: PASS**

### Brief analysis of findings relative to your focus.

The implementation includes a highly specific and comprehensive `pytest` suite that targets the most complex new features and critical edge cases, significantly improving the overall testability and reliability of the Agent CLI (Acceptance Criterion: Comprehensive `pytest` suite).

**Test Coverage Analysis (PASS):**

1.  **Core Utilities and Compliance**: The critical `scrub_sensitive_data` function (required for GDPR/SOC 2 compliance when communicating with LLMs) is fully covered in `tests/core/test_scrubber.py`, validating its PII and secret redaction capabilities.
2.  **AI Service Initialization**: `tests/core/test_ai.py` confirms the correct priority and fallback mechanism for AI providers (Gemini, OpenAI, GH CLI), ensuring the system remains functional even if preferred keys are missing.
3.  **Complex Governance Logic (`preflight`)**: `tests/commands/test_check_commands.py` verifies the robust `preflight` logic, including:
    *   **Chunking Logic**: Testing that the large diff is correctly split into chunks (9 roles * 2 chunks = 18 AI calls verified when using the constrained `gh` provider).
    *   **Verdict Aggregation**: Validation that a single `Verdict: BLOCK` from any role results in an overall exit code 1.
    *   **Safety**: Testing the regex parsing to prevent false-positive BLOCK verdicts from explanatory text.
4.  **New AI Commands**: `test_ai_commands.py` provides successful happy-path integration tests for `plan`, `new-runbook`, and `match-story`, ensuring they correctly interact with the mocked AI service and create artifacts in the correct locations.
5.  **Governance Structure Testability**: `test_runbook_prompt.py` specifically verifies the highly complex system prompt construction for `new-runbook`, ensuring that dynamic agent lists and the "Definition of Done" are correctly injected for AI processing.
6.  **Breaking Change Validation**: `tests/test_cli_options.py` confirms the intentional breaking change (`-v` removed) is correctly implemented, preventing it from showing the version.

**Edge Cases & Testability (PASS):**

*   **Token Limits**: The implementation actively manages token limits by splitting diffs in `check.py` and implements retry logic for GH CLI API rate limits in `agent.core.ai`, showing proactive handling of external service constraints.
*   **Modular Design**: The use of utility functions (`find_story_file`, `load_governance_context`) and service objects (`ai_service`) makes dependency injection straightforward for testing, greatly enhancing testability.

**Minor Finding (Non-Blocking):**

*   **`implement` Command Coverage**: While surrounding utilities and the AI service are well-tested, there is no dedicated test case for `agent implement` in `test_ai_commands.py` to confirm the specific prompt construction or file parsing logic for the Runbook execution workflow. This is mitigated by the strong coverage of the similar `plan` and `new-runbook` commands.

### ✅ @Docs: PASS

### ✅ @Observability: PASS

### ✅ @Backend: PASS

### ✅ @Mobile: PASS

### ✅ @Web: PASS

