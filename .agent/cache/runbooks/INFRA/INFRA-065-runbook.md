# INFRA-065: Add Vertex AI Provider to Agent CLI

## State

COMMITTED

## Goal Description

Enable the Agent CLI to use Vertex AI as an alternative provider to Gemini (AI Studio), allowing GCP users to leverage higher rate limits via Application Default Credentials (ADC) and improve scalability for production multi-agent workflows.

## Linked Journeys

- None

## Panel Review Findings

**@Architect**:

- PASS. The design correctly extends the existing provider pattern in `service.py` (`PROVIDERS` dict, `reload()`, `_try_complete()` branches). The `google-genai` SDK already supports both `api_key=` and `vertexai=True` modes via the same `genai.Client`, so this is a configuration-level change — no new SDKs or architectural boundaries are introduced.
- The factory extraction for `genai.Client` construction is mandatory per AC to eliminate duplication between the `gemini` branch in `reload()` and the per-request re-init in `_try_complete()`.
- No ADR required — this is an additive provider within the existing architecture.

**@QA**:

- PASS. Test strategy covers unit mocks of `genai.Client(vertexai=True)`, credential validation for `GOOGLE_CLOUD_PROJECT`, edge cases (ADC expired, project unset), and negative tests (invalid provider name). Existing test pattern in `test_validate_credentials.py` serves as a template.
- **ACTION**: Add `vertex` cases to `test_validate_credentials.py` and add `test_service.py` tests for the Vertex AI `_try_complete()` branch.
- E2E via `agent panel --panel-engine adk` with `provider: vertex` — manual verification in a GCP-authenticated environment.

**@Security**:

- PASS. Vertex AI uses short-lived OAuth2 tokens via ADC — strictly superior to long-lived API keys. No new secrets introduced. `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` logged at DEBUG level only (not INFO) to avoid leaking project IDs in public CI logs. This is a local CLI tool with no network endpoints, so the attack surface does not expand.
- **ACTION**: Vertex path must NOT silently fall back to `generativelanguage.googleapis.com` on ADC failure — it must fail hard with an actionable error.

**@Product**:

- PASS. Acceptance criteria are clear and testable. The four scenarios (vertex with ADC, gemini with key, neither set, both set with explicit precedence) cover all user-facing configurations. Error messages must be actionable — not raw `google.auth` tracebacks.

**@Observability**:

- PASS. The story requires startup logging of `Provider: vertex (aiplatform.googleapis.com, project=X, location=Y)` and structured logging of `{"event": "provider_fallback", ...}` on rate-limit fallbacks. Both are enforced in this runbook.
- **ACTION**: Add structured `extra={}` dict to all provider fallback log calls.

**@Docs**:

- PASS. `docs/getting_started.md` must be created with a side-by-side provider comparison table and Vertex AI setup instructions (ADC, env vars, API enablement).
- **ACTION**: Also update CHANGELOG.md with the new provider entry.

**@Compliance**:

- PASS. Apache 2.0 license headers required on all new/modified files. Vertex AI data processing governed by GCP ToS/DPA — no new personal data fields introduced. No PII logged.
- No GDPR lawful basis documentation required — this feature processes code/text, not personal data.

**@Mobile**:

- N/A. CLI-only change. No mobile impact.

**@Web**:

- N/A. CLI-only change. No web impact.

**@Backend**:

- PASS. The `google-genai` SDK (`genai.Client`) is already a dependency. The `vertexai=True` flag is the only new construction path. All public method signatures retain full type hints. Per ADR-028, Typer CLI commands are synchronous — `subprocess.run` usage is correct.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract `genai.Client` construction from `reload()` and `_try_complete()` into a shared `_build_genai_client()` factory method on `AIService`
- [ ] Add `vertex` to the fallback chain in `try_switch_provider()` (position: after `gemini`, before `openai`)

## Implementation Steps

### Core AI Config

#### [MODIFY] [config.py](file:///.agent/src/agent/core/config.py)

1. **`get_valid_providers()`** (line 364–368): Add `"vertex"` to the returned list:

```python
def get_valid_providers() -> List[str]:
    """
    Returns list of valid AI provider names.
    """
    return ["gh", "openai", "gemini", "vertex", "anthropic"]
```

1. **`Config._get_enabled_providers()`** (line 138–150): Add Vertex AI detection via `GOOGLE_CLOUD_PROJECT`:

```python
def _get_enabled_providers(self) -> List[str]:
    providers = []
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        providers.append("gemini")
    if os.getenv("GOOGLE_CLOUD_PROJECT"):
        providers.append("vertex")
    return providers
```

---

### Credential Validation

#### [MODIFY] [credentials.py](file:///.agent/src/agent/core/auth/credentials.py)

1. **`provider_key_map`** (line ~71): Add `"vertex"` entry mapping to `GOOGLE_CLOUD_PROJECT`:

```python
provider_key_map = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "vertex": ["GOOGLE_CLOUD_PROJECT"],
    "gh": ["GH_API_KEY", "GITHUB_TOKEN"]
}
```

> **Note**: For `vertex`, the "key" is `GOOGLE_CLOUD_PROJECT` — the actual authentication uses ADC, so we validate that the project ID is set. ADC token validation happens lazily at request time.

---

### AI Service

#### [MODIFY] [service.py](file:///.agent/src/agent/core/ai/service.py)

1. **`PROVIDERS` dict** (line 37–62): Add `vertex` entry:

```python
"vertex": {
    "name": "Google Vertex AI",
    "service": "vertex",
    "secret_key": None,   # Uses ADC, not API key
    "env_var": "GOOGLE_CLOUD_PROJECT",
},
```

1. **`AIService.__init__`** (line 73–84): Add `vertex` to `self.models` dict:

```python
self.models = {
    'gh': 'openai/gpt-4o',
    'gemini': 'gemini-pro-latest',
    'vertex': 'gemini-2.0-flash',   # Default model for Vertex AI
    'openai': os.getenv("OPENAI_MODEL", "gpt-4o"),
    'anthropic': 'claude-sonnet-4-5-20250929'
}
```

1. **New factory method** `_build_genai_client()` — add after `__init__`:

```python
def _build_genai_client(self, provider: str) -> "genai.Client":
    """
    Factory for google-genai Client construction.

    Eliminates duplication between gemini (api_key) and vertex (ADC) paths.
    Both use the same google-genai SDK — only the auth differs.
    """
    from google import genai
    from google.genai import types

    http_options = types.HttpOptions(timeout=600000)

    if provider == "vertex":
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT must be set for provider 'vertex'. "
                "Run: export GOOGLE_CLOUD_PROJECT=your-project-id"
            )
        try:
            client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
                http_options=http_options,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "credentials" in error_str or "auth" in error_str:
                raise ValueError(
                    "ADC authentication failed for Vertex AI. "
                    "Run: gcloud auth application-default login"
                ) from e
            raise
        logging.debug(
            "Provider: vertex (aiplatform.googleapis.com, "
            f"project={project}, location={location})"
        )
        return client

    elif provider == "gemini":
        gemini_key = get_secret("api_key", service="gemini")
        if not gemini_key:
            raise ValueError(
                "GEMINI_API_KEY must be set for provider 'gemini'."
            )
        client = genai.Client(
            api_key=gemini_key,
            http_options=http_options,
        )
        logging.debug(
            "Provider: gemini (generativelanguage.googleapis.com)"
        )
        return client

    else:
        raise ValueError(f"_build_genai_client: unsupported provider '{provider}'")
```

1. **`reload()`** (line 124–186): Add Vertex AI client initialization block (after Gemini block):

```python
# 1b. Check Vertex AI (ADC-based, no API key)
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    try:
        self.clients['vertex'] = self._build_genai_client("vertex")
    except ImportError:
        console.print(
            "[dim]ℹ️  GOOGLE_CLOUD_PROJECT set but google-genai package not installed. "
            "Install with: pip install google-genai[/dim]"
        )
    except ValueError as e:
        console.print(f"[yellow]⚠️  Vertex AI initialization failed: {e}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Vertex AI initialization failed: {e}[/yellow]")
```

Also refactor the existing Gemini block in `reload()` to use `_build_genai_client("gemini")`:

```python
# 1. Check Gemini
gemini_key = get_secret("api_key", service="gemini")
if gemini_key:
    try:
        self.clients['gemini'] = self._build_genai_client("gemini")
    except ImportError:
        console.print(
            "[dim]ℹ️  Gemini key found but google-genai package not installed. "
            "Install with: pip install google-genai[/dim]"
        )
    except Exception as e:
        console.print(f"[yellow]⚠️  Gemini initialization failed: {e}[/yellow]")
```

1. **`_set_default_provider()`** (line 234–261): Add `vertex` to the hardcoded fallback chain:

```python
# 2. Hardcoded Fallback Priority
if 'gh' in self.clients:
    self.provider = 'gh'
elif 'gemini' in self.clients:
    self.provider = 'gemini'
elif 'vertex' in self.clients:
    self.provider = 'vertex'
elif 'openai' in self.clients:
    self.provider = 'openai'
elif 'anthropic' in self.clients:
    self.provider = 'anthropic'
else:
    self.provider = None
```

1. **`try_switch_provider()`** (line 293–319): Add `vertex` to fallback chain:

```python
fallback_chain = ['gh', 'gemini', 'vertex', 'openai', 'anthropic']
```

1. **`_try_complete()`** (line 534–747): Add `vertex` branch. The Vertex AI path uses the same `genai.Client` API as Gemini but constructs via `_build_genai_client("vertex")`:

```python
elif provider == "vertex":
    from google.genai import types

    bg_client = self._build_genai_client("vertex")

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        http_options=types.HttpOptions(timeout=600000),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
    response_stream = bg_client.models.generate_content_stream(
        model=model_used,
        contents=user_prompt,
        config=config
    )

    full_text = ""
    for chunk in response_stream:
        if chunk.text:
            full_text += chunk.text

    return full_text.strip()
```

1. **`_try_complete()` exception handler** (line 678–684): Add `vertex` to `host_map`:

```python
host_map = {
    "openai": "api.openai.com",
    "gemini": "generativelanguage.googleapis.com",
    "vertex": "aiplatform.googleapis.com",
    "anthropic": "api.anthropic.com",
    "gh": "models.github.com"
}
```

1. **`get_available_models()`** (line 439–532): Add `vertex` branch (identical to `gemini` since both use `genai.Client`):

```python
elif target_provider == "vertex":
    client = self.clients['vertex']
    for model in client.models.list():
        model_id = model.name if hasattr(model, 'name') else str(model)
        display_name = (
            model.display_name
            if hasattr(model, 'display_name')
            else model_id
        )
        models.append({"id": model_id, "name": display_name})
```

1. **Startup logging**: In `_ensure_initialized()` after `self.reload()`, add:

```python
if self.provider:
    logging.info(f"AI Provider initialized: {self.provider}")
```

---

### Configuration

#### [MODIFY] [agent.yaml](file:///.agent/etc/agent.yaml)

No changes required to the default config. The existing `provider: gemini` remains the default. Users opt into Vertex by changing to `provider: vertex`. Add a comment for discoverability:

```yaml
agent:
  provider: gemini  # Options: gemini, vertex, openai, anthropic, gh
```

---

### Documentation

#### [NEW] [getting_started.md](file:///docs/getting_started.md)

Create `docs/getting_started.md` with:

- Provider comparison table (Gemini vs Vertex AI vs OpenAI vs Anthropic)
- Vertex AI setup instructions (ADC, env vars, API enablement)
- Side-by-side config examples
- Troubleshooting section (ADC expired, API not enabled, project ID missing)

#### [MODIFY] CHANGELOG.md

Add entry under next release:

```
### Added
- Vertex AI provider support (`provider: vertex` in agent.yaml) — uses ADC for authentication, providing higher rate limits for production use.
```

---

### Tests

#### [MODIFY] [test_validate_credentials.py](file:///.agent/src/agent/core/auth/tests/test_validate_credentials.py)

Add test cases for the `vertex` provider:

```python
def test_validate_credentials_vertex_has_project(clear_env, mock_secret_manager):
    """Should pass if GOOGLE_CLOUD_PROJECT is set for vertex provider."""
    mock_secret_manager.is_unlocked.return_value = True
    mock_secret_manager.get_secret.return_value = None
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project"}), \
         patch("agent.core.auth.credentials.LLM_PROVIDER", "vertex"):
        validate_credentials()  # Should not raise

def test_validate_credentials_vertex_missing_project(clear_env, mock_secret_manager):
    """Should fail if GOOGLE_CLOUD_PROJECT is missing for vertex provider."""
    mock_secret_manager.is_unlocked.return_value = True
    mock_secret_manager.get_secret.return_value = None
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "vertex"):
        with pytest.raises(MissingCredentialsError) as exc:
            validate_credentials()
        assert "GOOGLE_CLOUD_PROJECT" in str(exc.value)
```

#### [MODIFY] [test_service.py](file:///.agent/src/agent/core/ai/tests/test_service.py)

Add test cases for:

- `_build_genai_client("vertex")` with mocked `genai.Client(vertexai=True, ...)`
- `_build_genai_client("gemini")` with mocked `genai.Client(api_key=...)`
- `_try_complete("vertex", ...)` branch with mocked streaming response
- ADC failure produces actionable error (not raw traceback)
- Invalid provider name in `agent.yaml` produces graceful `ValueError`

#### [NEW] [test_vertex_provider.py](file:///.agent/src/agent/core/ai/tests/test_vertex_provider.py)

Dedicated test file for Vertex AI provider:

- Factory creates `genai.Client(vertexai=True, project=..., location=...)`
- Missing `GOOGLE_CLOUD_PROJECT` raises `ValueError` with actionable message
- ADC auth failure raises `ValueError` mentioning `gcloud auth application-default login`
- `GOOGLE_CLOUD_LOCATION` defaults to `us-central1`
- Vertex provider does NOT fall back to `generativelanguage.googleapis.com`

## Verification Plan

### Automated Tests

- [ ] `make test` passes with all existing tests unchanged
- [ ] New `test_validate_credentials_vertex_*` tests pass
- [ ] New `test_vertex_provider.py` tests pass
- [ ] `get_valid_providers()` returns list including `"vertex"`
- [ ] Invalid provider `provider: foobar` in agent.yaml raises `ValueError`

### Manual Verification

- [ ] Set `provider: vertex` in `agent.yaml`, set `GOOGLE_CLOUD_PROJECT`, run `agent panel` — completes via Vertex AI
- [ ] Set `provider: vertex` without `GOOGLE_CLOUD_PROJECT` — clear error message
- [ ] Expire ADC (`gcloud auth application-default revoke`) — actionable error referencing `gcloud auth application-default login`
- [ ] Set `provider: gemini` with `GEMINI_API_KEY` — existing behavior unchanged
- [ ] Set both credentials, explicit `provider: vertex` takes precedence
- [ ] Startup log shows `Provider: vertex (aiplatform.googleapis.com, project=X, location=Y)`

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] docs/getting_started.md created with provider comparison and Vertex AI setup
- [ ] Inline docstrings on `_build_genai_client()` factory method

### Observability

- [ ] Startup log: `Provider: vertex (aiplatform.googleapis.com, project=X, location=Y)` at DEBUG
- [ ] Rate-limit log: provider, model, retry count in structured `extra={}`
- [ ] Fallback log: `{"event": "provider_fallback", "from": "vertex", "to": "...", "reason": "..."}`
- [ ] Logs are PII-free (project ID at DEBUG only)

### Testing

- [ ] Unit tests passed (`make test`)
- [ ] Credential validation tests for `vertex` provider
- [ ] Factory method tests for both `gemini` and `vertex` construction paths
- [ ] Negative test: invalid provider name
