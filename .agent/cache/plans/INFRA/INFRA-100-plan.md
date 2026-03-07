# Plan: INFRA-100 Decompose AI Service Module

To address the monolithic 1,169 LOC `core/ai/service.py`, the decomposition will follow a "bottom-up" approach: defining interfaces first, extracting utility logic, implementing concrete providers, and finally refactoring the service into a lightweight facade.

## Child Stories

### INFRA-101: Define AI Protocols and Agnostic Exception Mappings
- **Description**: Establish the structural contract for all AI providers and define a provider-agnostic exception hierarchy to decouple the service from vendor-specific libraries.
- **Scope**: Create `core/ai/protocols.py` and `core/ai/exceptions.py`.
- **Acceptance Criteria**:
    - [ ] `AIProvider` protocol defined with `generate()`, `stream()`, and `supports_tools()` (AC-1).
    - [ ] Protocols use `@runtime_checkable` (AC-10).
    - [ ] Define custom exception classes (e.g., `AIConnectionError`, `AIRateLimitError`) used to wrap vendor-specific errors (AC-11).
    - [ ] PEP-484 and PEP-257 compliance (AC-8).
- **Estimated LOC**: ~100

### INFRA-102: Extract AI Streaming and Retry Infrastructure
- **Description**: Move streaming chunk processing and retry/backoff logic from the main service into a dedicated module.
- **Scope**: Create `core/ai/streaming.py`.
- **Acceptance Criteria**:
    - [ ] Streaming response handling and chunk processing logic moved from `service.py` (AC-3).
    - [ ] Retry/backoff decorators implemented using agnostic exceptions from INFRA-101 (AC-3, AC-11).
    - [ ] Unit tests in `tests/core/ai/test_streaming.py` covering malformed chunks and timeouts (AC-7, Negative Test).
- **Estimated LOC**: ~250

### INFRA-103: Implement OpenAI and Anthropic Provider Backends
- **Description**: Extract the OpenAI and Anthropic specific implementation logic into the new provider package.
- **Scope**: Create `core/ai/providers/openai.py` and `core/ai/providers/anthropic.py`.
- **Acceptance Criteria**:
    - [ ] Concrete classes implement `AIProvider` protocol (AC-2).
    - [ ] Logic for payload formatting and response parsing moved from `service.py`.
    - [ ] Consumers use `AIProvider` for type hints (AC-9).
    - [ ] Unit tests for both providers in `tests/core/ai/test_providers.py` (AC-7).
- **Estimated LOC**: ~350

### INFRA-104: Implement Vertex AI and Ollama Provider Backends
- **Description**: Extract the Vertex AI and Ollama specific implementation logic into the provider package.
- **Scope**: Create `core/ai/providers/vertex.py` and `core/ai/providers/ollama.py`.
- **Acceptance Criteria**:
    - [ ] Concrete classes implement `AIProvider` protocol (AC-2).
    - [ ] Logic for payload formatting and response parsing moved from `service.py`.
    - [ ] Unit tests for both providers in `tests/core/ai/test_providers.py` (AC-7).
    - [ ] Maintain existing OpenTelemetry spans for these providers (Observability NFR).
- **Estimated LOC**: ~300

### INFRA-105: Refactor AI Service Facade and Final Integration
- **Description**: Finalize the refactor of `core/ai/service.py` to act as a thin facade and ensure system-wide integrity.
- **Scope**: Refactor `core/ai/service.py` and `core/ai/providers/__init__.py` (factory).
- **Acceptance Criteria**:
    - [ ] `core/ai/service.py` reduced to < 500 LOC (AC-4).
    - [ ] Provider factory implemented to instantiate concrete backends based on configuration.
    - [ ] Circular dependency check: `python -c "import agent.cli"` (AC-6).
    - [ ] All existing tests pass (AC-5).
- **Estimated LOC**: ~200 (post-reduction)