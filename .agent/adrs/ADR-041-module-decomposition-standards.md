# ADR-041: Module Decomposition Standards

## Status

Proposed

## Date

2026-03-06

## Context

The agent codebase has grown to contain multiple files exceeding 1,500 LOC, with
the largest (`tui/app.py`, `core/governance.py`) approaching 2,000 lines. These
monolithic files mix unrelated concerns, making the codebase brittle, hard to
test in isolation, and prone to merge conflicts when multiple stories touch the
same file.

INFRA-099 (Structural Decomposition) proposes breaking these files apart, and
INFRA-098 (Unify Console and Voice Agent Interface Layer) depends on clear module
boundaries to extract a shared AgentSession interface. A formal architectural
standard is needed to guide both efforts and prevent future regression to
monolithic structures.

Beyond file splitting, the codebase needs **interface-first architecture** —
formal contracts (Python `Protocol` classes) that define capabilities, with
modular backends that implement them. This enables plugin-style extensibility
and ensures the console and voice agents can share a common interface layer.

## Decision

### 1. Module Size Ceilings

No Python source file in `.agent/src/` shall exceed **1,000 physical lines of code** (total lines, not logical statements). This is a hard limit strictly enforced by CI. 

Additionally, a **Warning Zone** starts at **500 physical lines of code**. Files exceeding 500 lines will generate warnings in the preflight checks, signaling that the file should be evaluated for logical "seams" to split.

The target "Goldilocks Zone" for all modules is **100–300 lines**.

**Exceptions:**
- `migrations/` directories
- Files containing `# nolint: loc-ceiling`

An architectural exception record must be documented when using the nolint tag.

**Rationale:** 
Most style guides and automated linting tools suggest these thresholds:
- The "Goldilocks" Zone (100–300 lines): Most well-architected files fall here. They are focused on a single responsibility.
- The Warning Zone (500 lines): Many Google and Airbnb style guides suggest that at 500 lines, you should start looking for logical "seams" to split the file.
- The Hard Limit (1,000 lines): This is often the default "error" threshold in CI/CD pipelines. Files larger than this are statistically more likely to contain bugs and are significantly harder for peer reviewers to parse.

### 2. Single Responsibility Modules

Each module must have a single, clearly defined responsibility expressible in one
sentence. The module docstring must state this responsibility.

```python
"""Prompt composition for the agent console.

Responsible for building system prompts from personality config,
repository context, and runtime context.
"""
```

### 3. Interface-First Design

Every decomposed package must define its public contract via a Python `Protocol`
class. Consumers depend on the protocol, never on concrete implementations.

**Rules:**
- Each package exposes one or more `Protocol` classes in its `__init__.py` or a
  dedicated `protocols.py` file.
- Concrete implementations live in separate modules within the package.
- Consumers import the protocol type for type annotations and the factory for
  instantiation. They never import concrete classes directly.
- New backends can be added by implementing the protocol — no changes to consumers.

**Example — AI Provider:**

```python
# core/ai/protocols.py
from typing import Protocol, AsyncIterator

class AIProvider(Protocol):
    """Contract for all AI provider backends."""
    async def generate(self, prompt: str, **kwargs) -> Response: ...
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[Chunk]: ...
    def supports_tools(self) -> bool: ...

# core/ai/providers/openai.py
class OpenAIProvider:  # implements AIProvider
    async def generate(self, prompt: str, **kwargs) -> Response: ...
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[Chunk]: ...
    def supports_tools(self) -> bool: return True

# core/ai/service.py — facade
from .protocols import AIProvider
def get_provider(name: str) -> AIProvider: ...
```

**Standard Protocols to establish:**

| Protocol | Package | Purpose |
|---|---|---|
| `AIProvider` | `core/ai/` | LLM provider abstraction (generate, stream, tools) |
| `AgentSession` | `core/session/` | Shared interface for TUI and voice (INFRA-098) |
| `ToolProvider` | `core/tools/` | Tool registration and execution contract |
| `GovernanceRole` | `core/governance/` | Role-specific review behaviour |
| `PromptBuilder` | `core/prompts/` | Prompt composition contract |

### 4. Decomposition Targets

The following decomposition boundaries are established:

#### TUI Layer (`agent/tui/`)

| Module | Responsibility |
|---|---|
| `app.py` | Textual TUI framework, widget layout, input/output |
| `prompts.py` | System prompt composition (personality, repo context, runtime) |
| `chat.py` | Chat loop, message history, ReAct engine integration |

#### Governance Layer (`agent/core/governance/`)

| Module | Responsibility |
|---|---|
| `protocols.py` | `GovernanceRole` protocol |
| `panel.py` | Council orchestration, agent dispatch, result aggregation |
| `roles.py` | Role definitions, prompt templates per role |
| `validation.py` | Finding validation, false positive filtering, reference checking |

#### Implementation Layer (`agent/core/implement/`)

| Module | Responsibility |
|---|---|
| `orchestrator.py` | Step processing, runbook execution flow |
| `circuit_breaker.py` | LOC tracking, thresholds, follow-up story generation |

#### AI Service Layer (`agent/core/ai/`)

| Module | Responsibility |
|---|---|
| `protocols.py` | `AIProvider` protocol definition |
| `service.py` | Public API facade, model selection, request routing |
| `streaming.py` | Stream handling, chunk processing, partial response assembly |
| `providers/` | One module per provider backend (openai, vertex, anthropic, ollama) |

### 5. Import Hygiene

- **No circular imports.** The dependency graph must be a DAG. Validated by
  `python -c "import agent.cli"` in CI.
- **Explicit re-exports.** Package `__init__.py` files define the public API via
  `__all__`. Internal modules are not imported directly by consumers outside the
  package.
- **Dependency direction:** `commands/` → `core/` → `utils/`. Never reverse.
- **Protocol imports only.** Cross-package type annotations must use Protocol types,
  not concrete implementations.

### 6. Type Hints and Documentation

All new modules created during decomposition must include:
- PEP-484 type hints on all public functions and methods
- PEP-257 docstrings on all public classes and functions
- Module-level docstring stating the single responsibility
- Protocol classes must include comprehensive docstrings explaining the contract

### 7. Enforcement

- **Pre-commit check:** A strict LOC counter (`scripts/check_loc.py`) and import checker (`scripts/check_imports.py`) run as pre-commit hooks and via `agent preflight --gate quality`.
- **Preflight gate:** @architect role validates module boundaries and protocol usage
- **CI validation:** `python -c "import agent.cli"` catches circular imports
- **Protocol coverage:** Every package in `core/` must expose at least one Protocol

## Consequences

### Positive
- Files become independently testable and reviewable
- Merge conflicts are reduced when parallel stories touch different subsystems
- New contributors can understand a module without reading 2,000 lines of context
- Enables INFRA-098 to extract shared interfaces from well-defined boundaries

### Negative
- More files to navigate (mitigated by clear package structure and IDE support)
- Import paths change across the codebase (one-time migration cost)
- Existing documentation references become stale (addressed by INFRA-099 AC-10)

### Risks
- Over-decomposition could lead to too many tiny files — the 500 LOC ceiling is a
  maximum, not a target. Modules should be as large as their responsibility requires.

## Related

- **INFRA-099**: Structural Decomposition (implements this ADR)
- **INFRA-098**: Unify Console and Voice Agent Interface Layer (depends on this ADR)
- **INFRA-012**: Refactor Codebase Utilities (superseded by INFRA-099)
- **ADR-040**: Agentic Tool-Calling Loop Architecture

## Copyright

Copyright 2026 Justin Cook
