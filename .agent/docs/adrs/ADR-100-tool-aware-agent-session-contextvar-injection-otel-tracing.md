# ADR-100: Tool-Aware AgentSession with ContextVar Injection and OTel Tracing

## Status

PROPOSED

## Date

2026-04-04

## Context

Prior to INFRA-146, `AgentSession` (`agent/core/session.py`) was a thin pass-through: it
forwarded the user prompt to the AI provider's `stream()` method and yielded text chunks.
Tool schemas were accepted in the constructor and forwarded to the provider, but no
tool-invocation loop existed — `tool_handlers` were stored but never called.

During INFRA-146 (LangChain decorator retirement), the following changes were introduced
without a preceding architectural review:

1. A full agentic tool-call loop was added to `AgentSession.stream_interaction`, allowing
   the session to detect `{"type": "tool_call"}` chunks, dispatch them via `tool_handlers`,
   and push results back into the conversation history for multi-turn tool use.
2. Each tool invocation was wrapped in an OpenTelemetry span (`tool.<name>`), making
   `AgentSession` the canonical source of per-tool telemetry.
3. `session_id` was added as a named parameter to five voice tool function signatures
   (`git.py`, `workflows.py`, `qa.py`, `fix_story.py`, `interactive_shell.py`), which
   caused the schema introspector in `registry.py` to expose `session_id` as an
   LLM-callable argument — a functional correctness bug.

The governance preflight panel (Backend role) flagged the `session.py` changes as an
unreviewed architectural decision and requested a formal ADR before the pattern is
accepted or rejected.

## Decision

**Accept the tool-aware `AgentSession` loop as the canonical pattern.** The revert
proposed by the governance panel is superseded by this ADR.

### Rationale

1. **Separation of concerns**: `AgentSession` is the natural boundary between the AI
   provider protocol and the rest of the system. It already owns the conversation history.
   Placing the tool-dispatch loop here avoids duplicating it in every consumer (TUI, voice,
   future web client).
2. **DRY telemetry**: A single OTel span site in `_dispatch_tool` (session layer) means all
   tool calls — regardless of which interface invoked them — emit spans with consistent
   attribute names (`tool.name`, `tool.args`, `tool.duration_ms`, `tool.success`).
3. **Provider agnosticism**: Providers return `{"type": "tool_call", "name": ..., "arguments": ...}`
   chunks as part of their stream. The session loop is the correct place to handle this
   uniformly rather than burdening each provider implementation.

### Constraints

- The `AgentSession` loop MUST NOT exceed `MAX_TOOL_ROUNDS = 10` per interaction.
- Tool dispatch MUST emit an OTel span via `tracer.start_as_current_span(f"tool.{name}")`.
- Tool dispatch MUST emit structured log events: `tool_dispatch_success` and
  `tool_dispatch_error`, per ADR-046.
- Providers that do not support tool calls MUST NOT return `{"type": "tool_call"}` chunks.
  The session loop handles their absence gracefully (zero tool rounds).

## Context Injection Pattern (replaces `RunnableConfig`)

`session_id` and other execution-context values MUST NOT appear in tool function
signatures, as they would be exposed to the LLM as callable parameters.

**Canonical pattern**: `contextvars.ContextVar` set by the orchestrator before dispatch.

```python
# agent/core/context.py
import contextvars
_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="unknown")

def get_session_id() -> str:
    return _session_id_var.get()

def set_session_id(sid: str) -> contextvars.Token:
    return _session_id_var.set(sid)
```

Tool functions call `get_session_id()` internally. The orchestrator calls
`set_session_id(self.session_id)` before initiating a session interaction. This is
thread-safe and async-safe; the `ContextVar` is propagated automatically into `asyncio`
tasks created within the same context.

```python
# VoiceOrchestrator.__init__
from agent.core.context import set_session_id
set_session_id(self.session_id)
```

## Relationship to Existing ADRs

- **ADR-046** (Structured Logging & Observability): Tool dispatch log events comply.
- **ADR-098** (AgentSession): This ADR is an extension to ADR-098, adding the tool loop.
  ADR-098 remains authoritative for session lifecycle.

## Alternatives Considered

### A. Keep OTel tracing in `tool_security.py` only
**Rejected.** `tool_security.py` is an audit/security wrapper, not the execution boundary.
Placing the primary span there means tools called outside the voice layer would not be
traced.

### B. Revert `session.py` and add per-consumer tool loops
**Rejected.** This was the governance panel's initial suggestion, superseded by this ADR.
Duplicating the dispatch loop in the TUI and voice orchestrator is worse than a shared
session-layer implementation.

### C. Pass `session_id` as a function parameter
**Rejected.** Exposes contextual data as an LLM-callable parameter. Causes schema
pollution and incorrect model behaviour.

## Consequences

**Positive:**
- Unified dispatch, tracing, and history management across all interfaces.
- No LangChain runtime dependency anywhere in the tool layer.
- `RunnableConfig` fully retired.

**Negative / Mitigations:**
- Providers must emit `{"type": "tool_call"}` chunks in a consistent format. A provider
  adaptation guide must be maintained (see `agent/core/ai/protocols.py`).
- `ContextVar` propagation is transparent in `asyncio` but must be explicitly documented 
  for contributors adding synchronous tool functions.

## Copyright

Copyright 2026 Justin Cook
