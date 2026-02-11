# ADR-025: Lazy AIService Initialization

## State

ACCEPTED

## Context

The `AIService` class (`agent.core.ai.service`) has a heavy `__init__` that initialises SDK clients (Google GenAI, OpenAI, Anthropic), runs subprocess calls (`gh --version`, `gh extension list`), and performs network-dependent secret lookups. When `ai_service = AIService()` is instantiated at module scope, **every** CLI command that transitively imports the module pays this cost — even commands like `sync`, `status`, and `--help` that never use AI.

This caused production crashes: `agent sync pull` would hang or fail because `AIService.__init__` attempted network calls in an environment where API keys were not configured.

## Decision

We adopt **lazy initialization** for `AIService`:

1. **`__init__` sets `self._initialized = False`** — no SDK clients are created.
2. **`_ensure_initialized()`** is called at the top of `complete()` and `get_available_models()`. It calls `reload()` exactly once on first use.
3. **Command files use local imports** (`from agent.core.ai import ai_service` inside the function body) to avoid triggering module-level instantiation during CLI startup.

### Constraints

- **Do NOT move `ai_service` imports back to module top-level.** This reintroduces the global init crash.
- **Do NOT remove the `_initialized` flag.** It is the standard lazy-init guard pattern.
- **Dependency injection** is a valid future improvement (ADR candidate) but is not required to solve the current problem.

## Alternatives Considered

- **Top-level init with try/except**: Silently swallowing errors hides misconfiguration and still incurs startup latency.
- **Singleton with `__new__`**: Adds complexity without solving the import-triggers-init problem.
- **Full DI framework**: Disproportionate overhead for a CLI tool; local imports achieve the same deferred resolution.

## Consequences

- **Positive**: Lightweight commands (`sync`, `status`, `--help`) execute instantly without network dependencies.
- **Positive**: AI-dependent commands initialise on first use with no behaviour change.
- **Negative**: Local imports are unconventional — this ADR exists to prevent reviewers from reverting them.
