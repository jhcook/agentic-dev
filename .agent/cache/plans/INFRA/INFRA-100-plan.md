# Plan: INFRA-100 Decompose AI Service Module

To decompose the 1,169 LOC `core/ai/service.py` into maintainable components under the 400 LOC threshold, the work is split into five logical phases: defining the interface, extracting shared utilities, migrating specific provider logic, and finally refactoring the facade.

## Child Stories

### INFRA-101: Define AI Provider Protocols and Types
- **Description**: Create the foundational interfaces and type definitions that will govern all AI provider implementations.
- **Scope**: Create `core/ai/protocols.py` and define the `AIProvider` Protocol. Ensure it is runtime-checkable and includes standard method signatures for `generate`, `stream`, and `supports_tools`.
- **Acceptance Criteria**:
    - AC-1: `core/ai/protocols.py` exists with `AIProvider` (PEP-544).
    - AC-9: Type hints use `AIProvider` protocol.
    - AC-10: Protocol is decorated with `@runtime_checkable`.
- **Estimated LOC**: < 100

### INFRA-102: Extract Streaming and Resilience Logic
- **Description**: Move stream processing and retry logic into a dedicated module to handle provider-agnostic resilience.
- **Scope**: Create `core/ai/streaming.py`. Extract chunk processing logic, backoff decorators, and custom exception mapping from `service.py`.
- **Acceptance Criteria**:
    - AC-3: `core/ai/streaming.py` contains chunk processing and retry logic.
    - AC-11: Decorators use provider-agnostic exceptions (e.g., `AIConnectionError` instead of `openai.APIError`).
    - AC-7: New unit tests in `tests/core/ai/test_streaming.py`.
- **Estimated LOC**: 250

### INFRA-103: Extract OpenAI Provider Implementation
- **Description**: Migrate the OpenAI-specific logic from the monolithic service into a standalone provider module.
- **Scope**: Create `core/ai/providers/openai.py`. Move OpenAI-specific configuration, client initialization, and generation logic into a class implementing `AIProvider`.
- **Acceptance Criteria**:
    - AC-2: `core/ai/providers/openai.py` is implemented.
    - AC-8: Full PEP-484 type hints and PEP-257 docstrings.
    - AC-10: Class explicitly satisfies the protocol.
- **Estimated LOC**: 300

### INFRA-104: Extract Anthropic, Vertex, and Ollama Providers
- **Description**: Migrate remaining provider backends into the new package structure.
- **Scope**: Create `core/ai/providers/anthropic.py`, `core/ai/providers/vertex.py`, and `core/ai/providers/ollama.py`. Ensure consistent implementation of the `AIProvider` protocol across all three.
- **Acceptance Criteria**:
    - AC-2: Implementation files created for Anthropic, Vertex, and Ollama.
    - AC-7: New unit tests in `tests/core/ai/test_providers.py`.
    - AC-8: Docstrings and type hints included.
- **Estimated LOC**: 350 (combined across 3 files)

### INFRA-105: Refactor AI Service Facade and Finalize
- **Description**: Transition `core/ai/service.py` to a thin facade that orchestrates the new modules.
- **Scope**: Refactor `core/ai/service.py` to import and delegate to the extracted providers. Remove all implementation details. Ensure no circular imports and verify all existing tests pass.
- **Acceptance Criteria**:
    - AC-4: `core/ai/service.py` reduced to < 500 LOC (target ~200 LOC).
    - AC-5: All existing behavioral tests pass.
    - AC-6: `python -c "import agent.cli"` succeeds (no circular imports).
    - Negative Test: Graceful handling of malformed chunks verified.
- **Estimated LOC**: 200 (remaining logic + imports)

## Dependency Graph
1. **INFRA-101** (Protocols) must be completed first.
2. **INFRA-102** (Streaming) and **INFRA-103/104** (Providers) can be worked on in parallel once protocols are defined.
3. **INFRA-105** (Facade) is the final integration step.