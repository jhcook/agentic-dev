# STORY-ID: INFRA-025: Integrate Anthropic Claude Provider

## State
ACCEPTED

## Goal Description
Integrate Anthropic Claude as a supported provider in the agent framework to enhance AI-assisted development workflows. This includes the addition of SDK support, configurable environment variables for API keys, router configurations for model metadata, and observability enhancements to track provider usage. This implementation will also improve resilience through added provider failover capabilities.

## Panel Review Findings
- **@Architect**:  
  The story aligns well with the modular architecture of the existing framework. Adding Claude could be implemented as an isolated module with minimal impact on other components. However, attention should be paid to the fallback chain logic to ensure no unintended performance degradation occurs when switching providers.

- **@Security**:  
  The requirement to source the API key from the environment is critical to maintaining security. Ensure there is no leakage of sensitive information, especially in logs. Additionally, the SDK must be vetted to ensure it doesn’t introduce vulnerabilities.

- **@QA**:  
  The acceptance criteria are clear and testable. However, the framework needs automated regression tests for provider switching. Additional mock tests for SDK calls and configuration validation are necessary, especially for edge cases like missing API keys or misconfigured routers.

- **@Docs**:  
  Documentation updates need to include details on how to configure Anthropic Claude, such as adding related environment variables, and any relevant details about its API. Clear, step-by-step examples for users will be necessary to ensure smooth adoption.

- **@Compliance**:  
  The implementation aligns with compliance rules, particularly if there is no PII logged and API keys remain secure. Additionally, since SDK-based external API integrations carry risks, include a compliance review for licensing (if applicable). Confirm linkage and alignment with ADR-001 or add a new ADR outlining Anthropic-specific considerations.

- **@Observability**:  
  The addition of the new provider's metrics to the Prometheus tracking system is sufficient for observability. Structured logging for outcomes (success/failure) of completion requests will improve root-cause identification during debugging.

## Implementation Steps
### Update Provider Configuration
#### [MODIFY] [config.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/config.py)
- Update `get_provider_config()` function to include Anthropic provider configuration:
  ```python
  "anthropic": {"api_key": os.getenv("ANTHROPIC_API_KEY")}
  ```
- Update `get_valid_providers()` function to include `"anthropic"` in the return list:
  ```python
  return ["gh", "openai", "gemini", "anthropic"]
  ```

---

### Add Router Configuration
#### [MODIFY] [router.yaml](file:///Users/jcook/repo/agentic-dev/.agent/etc/router.yaml)
- Add Anthropic model configurations following the existing model format:  
  ```yaml
  # --- Anthropic Claude 4.5 Models ---
  claude-sonnet-4-5:
    provider: "anthropic"
    deployment_id: "claude-sonnet-4-5-20250929"
    tier: "advanced"
    context_window: 200000
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015

  claude-haiku-4-5:
    provider: "anthropic"
    deployment_id: "claude-haiku-4-5-20250929"
    tier: "standard"
    context_window: 200000
    cost_per_1k_input: 0.001
    cost_per_1k_output: 0.005

  claude-opus-4-5:
    provider: "anthropic"
    deployment_id: "claude-opus-4-5-20250929"
    tier: "premium"
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075
  ```

---

### Modify Service Implementation
#### [MODIFY] [service.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/ai/service.py)
- Add Anthropic SDK installation to dependencies (add to package manager)
- Add Anthropic client initialization in `__init__()` method (after line 76):
  ```python
  # 4. Check Anthropic
  anthropic_key = os.getenv("ANTHROPIC_API_KEY")
  if anthropic_key:
      try:
          from anthropic import Anthropic
          # Set 120s timeout for large contexts
          self.clients['anthropic'] = Anthropic(api_key=anthropic_key, timeout=120.0)
      except (ImportError, Exception) as e:
          console.print(f"[yellow]⚠️  Anthropic initialization failed: {e}[/yellow]")
  ```
- Update `models` dict to include Anthropic default model (after line 49):
  ```python
  'anthropic': 'claude-sonnet-4-5-20250929'
  ```
- Update fallback chain in `try_switch_provider()` to include Anthropic (line 150):
  ```python
  fallback_chain = ['gh', 'gemini', 'openai', 'anthropic']
  ```
- Add Anthropic handler in `_try_complete()` method (after OpenAI handler, around line 293):
  ```python
  elif provider == "anthropic":
      client = self.clients['anthropic']
      full_text = ""
      # Use streaming to prevent timeouts with large contexts (similar to Gemini)
      with client.messages.stream(
          model=model_used,
          max_tokens=4096,
          system=system_prompt,
          messages=[
              {"role": "user", "content": user_prompt}
          ]
      ) as stream:
          for text in stream.text_stream:
              full_text += text
      return full_text.strip()
  ```

---

### Observability Enhancements
#### Note on Metrics
- The existing Prometheus counter in [service.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/ai/service.py) (line 30-34) already supports per-provider tracking
- Once Anthropic is integrated, the existing code at line 214 will automatically track Anthropic usage:
  ```python
  ai_command_runs_total.labels(provider=current_p).inc()
  ```
- No additional metrics code changes required

#### Logging
- The existing structured logging (lines 205, 211, 218, 222) already handles new providers automatically
- Security pre-check at line 193 applies to all providers including Anthropic

## Verification Plan
### Automated Tests
**Test File**: [test_ai_service.py](file:///Users/jcook/repo/agentic-dev/.agent/src/tests/test_ai_service.py)

Run tests with: `cd .agent/src && pytest tests/test_ai_service.py -v`

- [ ] **Unit Test - Valid Provider**: Add test `test_set_anthropic_provider()` that mocks Anthropic client and verifies `set_provider("anthropic")` works correctly
- [ ] **Unit Test - Unconfigured Provider**: Existing `test_set_unconfigured_provider()` should be extended to test Anthropic when not configured
- [ ] **Unit Test - Completion**: Add test `test_anthropic_completion()` that mocks Anthropic client and verifies `_try_complete()` returns expected content
- [ ] **Unit Test - Fallback Chain**: Extend existing `test_fallback_logic()` to include Anthropic in the fallback sequence
- [ ] **Unit Test - Metrics**: Existing `test_metrics_increment()` pattern should be replicated for Anthropic provider
- [ ] **Integration Test**: Run `env -u VIRTUAL_ENV uv run agent impact --provider anthropic` with valid `ANTHROPIC_API_KEY` to verify end-to-end functionality

### Manual Verification
- [ ] Configure environment variable `ANTHROPIC_API_KEY` and manually test output from commands utilizing Anthropic Claude.
- [ ] Verify structured logs for clarity and absence of sensitive data.
- [ ] Test fallback chain manually by simulating provider failures in sequence.

## Definition of Done
### Documentation
- [ ] Add configuration information related to Anthropic (environment variables, usage examples) in `README.md`.
- [ ] Update `CHANGELOG.md` with a note about Anthropic integration.
- [ ] If applicable, add details in API Documentation (especially for endpoints influenced by new provider logic).

### Observability
- [ ] Add and verify Prometheus counters for tracking usage (`ai_command_runs_total` by `provider=anthropic`).
- [ ] Ensure structured logs align with compliance requirements, avoiding sensitive data.

### Testing
- [ ] Unit tests cover all new/modified code paths, with 90%+ coverage.
- [ ] All tests (unit, integration, regression) pass in CI/CD pipeline.
- [ ] Edge cases like missing/invalid API key and failed provider switches are verified.

### Compliance
- [ ] Review licensing and export compliance of the Anthropic SDK.
- [ ] Ensure alignment with ADR-001 and update ADRs if needed.

### Deployment Readiness
- [ ] Feature toggles, if implemented, allow for enabling/disabling Anthropic integration with minimal disruption.
- [ ] All changes validated in a staging environment before production deployment.