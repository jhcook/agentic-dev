This decomposition breaks the 812 LOC refactor into four manageable stories, ensuring each module remains within the 400 LOC limit (and targeting the 500 LOC total package limit requested in the ADR).

### Decomposition Plan

1.  **INFRA-108.1: Provider Package Scaffolding & Tier 1 Implementations**
    *   Setup the directory structure and the registry.
    *   Implement OpenAI and Anthropic providers (the most complex).
2.  **INFRA-108.2: Secondary Provider Implementations (Vertex, Ollama, GH)**
    *   Implement the remaining providers.
    *   Ensure all implement the `AIProvider` protocol.
3.  **INFRA-108.3: Service Layer Dispatch & Error Handling Refactor**
    *   Update `service.py` to use the factory.
    *   Standardize `AIRateLimitError` across providers.
4.  **INFRA-108.4: Unit Testing & Circular Dependency Validation**
    *   Provide isolated tests for each class.
    *   Validate the fix for circular imports and finalize the removal of the legacy file.

---

### INFRA-108.1: Provider Package Scaffolding & Tier 1 Implementations
**Description**: Create the `core/ai/providers/` package and implement the two primary providers (OpenAI, Anthropic).
**Acceptance Criteria**:
- [ ] Create `core/ai/providers/` with `__init__.py` containing the `get_provider(name: str)` factory.
- [ ] Implement `OpenAIProvider` in `core/ai/providers/openai.py` (Protocol-compliant).
- [ ] Implement `AnthropicProvider` in `core/ai/providers/anthropic.py` (Protocol-compliant).
- [ ] Registry in `__init__.py` maps strings to provider classes.
- [ ] Logic for `core.secrets` integration is encapsulated in the constructor.
**Estimated LOC**: ~250

### INFRA-108.2: Secondary Provider Implementations (Vertex, Ollama, GH)
**Description**: Implement the remaining provider backends using the same protocol-based structure.
**Acceptance Criteria**:
- [ ] Implement `VertexProvider` in `core/ai/providers/vertex.py`.
- [ ] Implement `OllamaProvider` in `core/ai/providers/ollama.py`.
- [ ] Implement `GitHubProvider` in `core/ai/providers/gh.py`.
- [ ] Register all new providers in the `PROVIDERS` registry.
- [ ] Ensure `extra` logging context is preserved in each implementation.
**Estimated LOC**: ~250

### INFRA-108.3: Service Layer Dispatch & Error Handling Refactor
**Description**: Refactor the main `AIService` to use the new provider classes and modernize error handling.
**Acceptance Criteria**:
- [ ] Modify `core/ai/service.py` to replace `if/elif` blocks with `get_provider(model_name)`.
- [ ] Refactor `_should_retry()` to catch `protocols.AIRateLimitError`.
- [ ] Each provider class must map its specific SDK errors (e.g., `openai.RateLimitError`) to `protocols.AIRateLimitError`.
- [ ] Remove the legacy `core/ai/providers.py` file.
- [ ] Verify package LOC total is < 500 (ADR-041).
**Estimated LOC**: ~150

### INFRA-108.4: Unit Testing & Circular Dependency Validation
**Description**: Ensure behavioral equivalence and system stability through isolated testing and import checks.
**Acceptance Criteria**:
- [ ] Unit tests for each concrete provider in `tests/core/ai/providers/` using mocked SDKs.
- [ ] Integration test for the `get_provider` factory.
- [ ] Verify `python -c "import agent.cli"` completes without circular import errors.
- [ ] All existing regression tests in `tests/core/ai/` pass.
**Estimated LOC**: ~300 (Test code)