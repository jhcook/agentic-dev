# STORY-ID: INFRA-044: Fail Fast on Missing Credentials

## State

ACCEPTED

## Goal Description

Create a "fail fast" mechanism that verifies the presence of necessary credentials during runtime for commands requiring authentication (e.g., admin console, AI integrations). If credentials are missing, the system should exit gracefully with an actionable and secure error message. The mechanism must ensure no sensitive information is exposed, maintain compliance with governance rules, and enhance usability without disrupting unrelated functionalities.

## Panel Review Findings

## Architect (@architect)

**Sentiment**: Positive
**Advice**:

- [ ] **Centralization**: Implement the credential check in a centralized location (e.g., `agent.core.auth` or a startup hook) rather than scattered across individual commands.
- [ ] **CLI Standards**: Ensure error messages follow proper CLI output standards (ADR-016). Use structured exits (`sys.exit(1)`) with user-friendly messages.
**Deep Dive**: Consider adding a `validate_credentials()` dependency that can be injected into commands that require it, ensuring lazy loading so commands that don't need credentials (like `agent version`) remain fast.

## Security (@security)

**Sentiment**: Positive
**Advice**:

- [ ] **Secret Leakage**: Ensure the error message specifically names the *missing* key (e.g., "OPENAI_API_KEY") but **never** logs or prints the values of present keys.
- [ ] **Hint Safety**: The "hint" to unlock the store should be safe to copy-paste.
**Deep Dive**: Critical to ensure that failing fast doesn't dump the entire environment or configuration state to the console, which might inadvertently hide sensitive data in a stack trace.

## Product (@product)

**Sentiment**: Positive
**Advice**:

- [ ] **Clarity**: The "Value" in the User Story is high. The "hint" is the most critical part for UX.
- [ ] **Onboarding Loop**: If possible, suggest running `agent onboard` again if that can fix the missing credentials.
**Deep Dive**: This directly addresses a known pain point. Ensure the error message distinguishes between "Credentials missing" vs "Credentials invalid". The story currently implies "missing" (locally), effectively covering local env vars or keyring state.

## QA (@qa)

**Sentiment**: Neutral
**Advice**:

- [ ] **Testability**: The Test Strategy needs to clarify how to *mock* the secret store in automated tests. We don't want tests failing because the CI runner doesn't have a system keyring.
- [ ] **Matrix**: Verify behavior across different OSs if using system keyrings.
**Deep Dive**: Please verify that the "fail fast" doesn't break the `help` command. We must be able to run `agent --help` without crashing even if credentials are missing.

## Observability (@observability)

**Sentiment**: Positive
**Advice**:

- [ ] **Log Levels**: Ensure this failure is logged as an `ERROR` but presented cleanly to the stdout (no raw stack traces for expected configuration errors).
**Deep Dive**: N/A

## Backend (@backend)

**Sentiment**: Positive
**Advice**:

- [ ] **Performance**: Be mindful of import costs. Checks should happen *after* command parsing but *before* heavy logic execution.
**Deep Dive**: Use `fastapi` dependency injection or `typer` callbacks if applicable to the CLI structure.

## Implementation Steps

### agent.core.auth

#### [NEW] .agent/src/agent/core/auth/**init**.py

- Create empty init file to define the module.

#### [NEW] .agent/src/agent/core/auth/credentials.py

- Create a `validate_credentials()` function.
- **Logic**:
  1. Determine active/configured providers (from Config or check basic/common keys like OpenAI/Anthropic/Gemini).
  2. For each required key:
     - **Step A**: Check `os.getenv(KEY_NAME)`. If present, valid.
     - **Step B**: Check `SecretManager.get_secret(service, key)`. If present, valid.
  3. If *neither* source has the key, verify "availability" (e.g., is the Secret Manager locked vs empty).
  4. Collect all missing keys.
  5. If missing keys exist -> Raise `MissingCredentialsError`.

#### [NEW] .agent/src/agent/core/auth/errors.py

- Define `MissingCredentialsError(Exception)`.
- Implement `__str__` to format a standard CLI error message (ADR-016 compliant).
  - List missing keys.
  - Suggest actionable resolution (Env var setup OR Secret Store unlock).
  - **Security**: Ensure NO values are printed.

#### [NEW] .agent/src/agent/core/auth/tests/test_validate_credentials.py

- Test scenarios:
  - All keys present in Env.
  - All keys present in Secret Store.
  - Keys missing in both.
  - Secret Store locked behavior.
  - Mock `os.getenv` and `SecretManager`.

---

### agent.commands

#### [MODIFY] .agent/src/agent/commands/admin.py

- In `pid_start()` (or `start()` command):
  - Call `validate_credentials()` *before* launching subprocesses.
  - Catch `MissingCredentialsError`: print friendly error and exit(1).

#### [MODIFY] .agent/src/agent/main.py

- Identify AI-dependent commands (`new-story`, `runbook`, `implement`, `fix`, `chat`).
- Inject `validate_credentials()` check at the start of these command handlers.
- **Note**: Do NOT add to global `cli` callback to preserve `agent --help` and `agent version`.

---

### config

#### [MODIFY] .agent/src/agent/core/config.py

- (Optional) Ensure `config` object exposes which providers are "enabled" so `validate_credentials` knows what to check.

---

### Docs Updates

#### [MODIFY] README.md

- Add "Troubleshooting: Missing Credentials" section.
- Explain the precedence (Env Var > Secret Store).

---

## Verification Plan

### Automated Tests

- [ ] **Unit Tests**: `pytest src/agent/core/auth/tests/` covering strict credential resolution order and error formatting.
- [ ] **Mocking**: Ensure tests pass in CI/CD (which lacks real secret store) by mocking `keyring` and `SecretManager`.

### Manual Verification

- [ ] **Scenario 1 (No Creds)**:
  - Clear env vars and rename `.agent/secrets` (temporarily).
  - Run `agent admin start`.
  - Expect: **Fail Fast** with explicit error listing missing keys.
- [ ] **Scenario 2 (Env Only)**:
  - Export `OPENAI_API_KEY=sk-fake...`.
  - Run `agent admin start`.
  - Expect: Pass credential check (backend process starts).
- [ ] **Scenario 3 (Store Only)**:
  - Unset Env. Setup Secret Store.
  - Run `agent admin start`.
  - Expect: Pass.
- [ ] **Scenario 4 (Mixed)**:
  - Env has one key, Store has another.
  - Expect: Pass.
- [ ] **Scenario 5 (Agent Version)**:
  - Run `agent version` with NO credentials.
  - Expect: Pass (no check performed).

## Definition of Done

### Documentation

- [ ] README.md updated with "Fail Fast" behavior and troubleshooting.

### Code Quality

- [ ] Code follows `agent.core.auth` centralization pattern.
- [ ] No PII/Secrets in logs or output.
- [ ] ADR-016 compliant error messages.

### Testing

- [ ] Unit tests added and passing.
- [ ] Manual verification checklist completed.
