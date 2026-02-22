# INFRA-014: AI Provider Selection and Validation

## Status
ACCEPTED

## Goal Description
To enhance AI-powered CLI commands (`implement`, `match-story`, `new-runbook`, `pr`) by adding a `--provider` option. This allows developers to explicitly select an AI provider (`gh`, `gemini`, `openai`). The system must validate the chosen provider against a list of supported options and verify that the necessary API keys or configurations are present before proceeding, raising specific errors for invalid or unconfigured providers.

## Panel Review Findings
- **@Architect**: The proposed design of adding validation directly into `ai_service.set_provider()` is sound and centralizes the logic. However, hardcoding the `VALID_PROVIDERS` whitelist in the service creates a tight coupling with the configuration system. A more robust approach would be to derive the list of valid providers dynamically from the keys present in the application's configuration structure. This ensures that adding a new provider only requires a configuration change, not a code change in the service layer. The choice of `ValueError` for an invalid name and `RuntimeError` for a configuration issue is appropriate as it clearly distinguishes between a user input error and an environment setup error.

- **@Security**: The explicit validation against a whitelist is a critical security control, preventing any form of injection or attempts to call arbitrary code through the provider parameter. The implementation must ensure that the user-provided string is used *only* for lookup against the whitelist and not for dynamic class loading or file path construction. The change also touches configuration handling; ensure that the process of checking for provider keys (e.g., `OPENAI_API_KEY`) does not log or expose these secrets in case of an error. Error messages for `RuntimeError` should be generic, like "Provider 'openai' is not configured," without revealing any configuration details.

- **@QA**: The test plan needs to be more comprehensive. We must cover the "happy path" for each supported provider. Crucially, we need to test the failure modes meticulously:
    1.  **Invalid Provider**: Test with a completely unsupported name (e.g., `--provider=anthropic`). Expect a `ValueError`.
    2.  **Case-Insensitivity**: Does `--provider=Gemini` work? The validation should be case-insensitive for user-friendliness but canonicalized internally.
    3.  **Unconfigured Provider**: Test with a valid provider (e.g., `openai`) but with its corresponding API key missing from the environment/config. Expect a `RuntimeError`.
    4.  **Default Behavior**: What happens if the `--provider` flag is omitted? The default provider (`gh`) should be used without error, assuming it is configured. This fallback logic must be explicitly tested.
    5.  **All Commands**: Verify the new option works and is validated correctly across all four commands (`implement`, `match-story`, `new-runbook`, `pr`).

- **@Docs**: The story correctly identifies the need to update `commands.md`. This documentation must clearly list the accepted values for the `--provider` option (`gh`, `gemini`, `openai`). It is essential to also document the default behavior (i.e., which provider is used if the flag is omitted) and the prerequisites for using each provider (e.g., "To use 'gemini', you must set the `GEMINI_API_KEY` environment variable.").

- **@Compliance**: The proposed changes are internal to the CLI tool and do not modify external API contracts. Therefore, `api-contract-validation.mdc` is not applicable. No new ADR is proposed, so `adr-standards.mdc` is also not directly relevant. The change allows users to select third-party AI providers, which may have different data privacy and processing policies. While outside the scope of this ticket, the documentation should subtly guide users to be aware of the data handling policies of the provider they select. No compliance violations are identified.

- **@Observability**: To understand the usage patterns and troubleshoot provider-specific issues, we must enhance our logging. Every call to the `ai_service` that invokes an AI model should have a structured log entry that includes the `provider` used for that specific call. Furthermore, we should introduce a new metric, a counter with a `provider` label (e.g., `ai_command_runs_total{provider="openai"}`), to track the usage of each AI provider over time. This will be invaluable for cost analysis and performance monitoring.

## Implementation Steps
### agent/services/ai_service.py
#### MODIFY agent/services/ai_service.py
- Add a new set of valid providers and a private attribute to store the current provider.
- Implement the `set_provider` method with validation logic.
- Update `_get_llm_client` to use the selected provider.

```python
# agent/services/ai_service.py
from agent.config import cfg
# ... other imports

VALID_PROVIDERS = {"gh", "openai", "gemini"}

class AIService:
    def __init__(self):
        # ... existing __init__ ...
        self._provider = "gh"  # Default provider
        self.set_provider(cfg.default_ai_provider) # Initialize with configured default

    def set_provider(self, provider: str):
        """
        Sets and validates the AI provider.

        Args:
            provider: The name of the provider to use ('gh', 'openai', 'gemini').

        Raises:
            ValueError: If the provider name is not in VALID_PROVIDERS.
            RuntimeError: If the provider is valid but not configured.
        """
        provider_lower = provider.lower()
        if provider_lower not in VALID_PROVIDERS:
            raise ValueError(f"Invalid AI provider '{provider}'. Must be one of {VALID_PROVIDERS}")

        if provider_lower == "openai" and not cfg.openai_api_key:
            raise RuntimeError("OpenAI provider is not configured. Please set OPENAI_API_KEY.")
        if provider_lower == "gemini" and not cfg.gemini_api_key:
            raise RuntimeError("Gemini provider is not configured. Please set GEMINI_API_KEY.")
        # 'gh' is assumed to be configured via gh cli auth. Add check if needed.

        self._provider = provider_lower

    def _get_llm_client(self):
        """Returns the appropriate LLM client based on the selected provider."""
        if self._provider == "openai":
            # logic to return OpenAI client
            return self._get_openai_client()
        elif self._provider == "gemini":
            # logic to return Gemini client
            return self._get_gemini_client()
        else: # Default to "gh"
            # logic to return GitHub Copilot client
            return self._get_gh_client()

    # ... rest of the service methods (e.g., implement, get_pr_summary) should use self._get_llm_client()
```

### [CLI Command Files]
#### MODIFY agent/cli/commands/implement.py
- Add the `--provider` Click option to the command decorator.
- In the command function, call `ai_service.set_provider()`.

```python
# agent/cli/commands/implement.py
import click
from agent.services.ai_service import AIService

@click.command()
@click.option('--provider', type=str, default='gh', help='The AI provider to use (gh, gemini, openai).')
# ... other options ...
def implement(provider, ...):
    """Implements a feature based on a user story."""
    try:
        ai_service = AIService()
        ai_service.set_provider(provider)
        # ... rest of the command logic ...
    except (ValueError, RuntimeError) as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

```
#### MODIFY agent/cli/commands/match_story.py, new_runbook.py, pr.py
- Apply the same changes as above to each of these files, adding the `--provider` option and the call to `ai_service.set_provider()` within a `try...except` block.

### tests/test_ai_service.py
#### NEW tests/test_ai_service.py
- Create a dedicated test file for `AIService` or add to an existing one. Add tests for the `set_provider` logic.

```python
# tests/test_ai_service.py
import pytest
from unittest.mock import patch
from agent.services.ai_service import AIService

def test_set_provider_valid():
    """Tests setting a valid, configured provider."""
    service = AIService()
    service.set_provider("gh")
    assert service._provider == "gh"

@patch('agent.config.cfg.openai_api_key', 'test-key')
def test_set_provider_openai_configured(mock_config):
    """Tests setting openai when it is configured."""
    service = AIService()
    service.set_provider("openai")
    assert service._provider == "openai"

def test_set_provider_invalid_raises_value_error():
    """Tests that an invalid provider name raises ValueError."""
    service = AIService()
    with pytest.raises(ValueError, match="Invalid AI provider 'foo'"):
        service.set_provider("foo")

@patch('agent.config.cfg.openai_api_key', None)
def test_set_provider_unconfigured_raises_runtime_error(mock_config):
    """Tests that a valid but unconfigured provider raises RuntimeError."""
    service = AIService()
    with pytest.raises(RuntimeError, match="OpenAI provider is not configured"):
        service.set_provider("openai")

```

## Verification Plan
### Automated Tests
- [ ] Test that `AIService` defaults to the 'gh' provider on initialization.
- [ ] Test `ai_service.set_provider('openai')` succeeds when `cfg.openai_api_key` is set.
- [ ] Test `ai_service.set_provider('gemini')` succeeds when `cfg.gemini_api_key` is set.
- [ ] Test `ai_service.set_provider('invalid_provider')` raises `ValueError`.
- [ ] Test `ai_service.set_provider('openai')` raises `RuntimeError` when `cfg.openai_api_key` is not set.
- [ ] Test `ai_service.set_provider('gemini')` raises `RuntimeError` when `cfg.gemini_api_key` is not set.
- [ ] Test that the `implement` command fails gracefully with a clear error message when an invalid provider is passed.
- [ ] Test that the `pr` command successfully runs using the `--provider=openai` option (requires mocking the API key and client).

### Manual Verification
- [ ] Run `env -u VIRTUAL_ENV uv run agent implement --help` and verify the `--provider` option is listed with its help text.
- [ ] Configure the OpenAI API key in your environment. Run `env -u VIRTUAL_ENV uv run agent implement --story="a simple feature" --provider=openai`. Verify it runs without errors.
- [ ] Do not configure the Gemini API key. Run `env -u VIRTUAL_ENV uv run agent pr --provider=gemini`. Verify the command fails with a "Gemini provider is not configured" error message.
- [ ] Run `env -u VIRTUAL_ENV uv run agent match-story --provider=foobar`. Verify the command fails with an "Invalid AI provider 'foobar'" error message.
- [ ] Run `env -u VIRTUAL_ENV uv run agent new-runbook` without the `--provider` flag. Verify it defaults to the 'gh' provider and executes successfully.

## Definition of Done
### Documentation
- [ ] `CHANGELOG.md` updated with a summary of the new feature.
- [ ] `docs/commands.md` updated to document the `--provider` option, its accepted values, and the configuration requirements for each.
- [ ] API Documentation updated (if applicable)

### Observability
- [ ] Logs generated by AI service calls are structured and include a `provider` field (e.g., `{"event": "ai_call_start", "provider": "openai", ...}`).
- [ ] A Prometheus counter metric `ai_command_runs_total` with a `provider` label is implemented and incremented on each successful AI command execution.

### Testing
- [ ] Unit tests passed
- [ ] Integration tests passed