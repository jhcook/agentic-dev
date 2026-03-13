# ADR-098: Unified Agent Interface Layer (AgentSession)

## Status

ACCEPTED

## Context

Currently, the `agent console` (TUI) and `agent admin` (Voice) use different logic to interact with AI models and execute tools. 
- The TUI uses `agent.core.engine.executor.AgentExecutor` and custom Python tool functions (`LocalToolClient`).
- The Voice Agent uses LangGraph (`create_react_agent`) and a separate set of LangChain tools (`backend.voice.tools.registry`).

This duplication means fixes applied to the TUI (like timeout configurations or prompt formatting) do not propagate to the Voice Agent.

## Decision

We will use the protocol-based AI interface built in INFRA-108 (`agent.core.ai.protocols.AIProvider`) as the foundation for a unified `AgentSession`. This abstracts away the orchestrator engine (AgentExecutor vs LangGraph) by providing a uniform way to register tools, inject system prompts, and stream interactions, relying purely on the AI provider's capabilities.

## Alternatives Considered

- Option A: Implement LangGraph for both interfaces. This would add heavy dependencies to the TUI and overcomplicate simple interactions.
- Option B: Maintain the status quo. This leads to continued logic duplication and divergent behavior between TUI and Voice interfaces.

## Consequences

- Positive: Shared tool schemas, unified timeout handling, and consistent behavior across both TUI and Voice interfaces. A single place to add OpenTelemetry tracing for agent loops.
- Negative: Requires refactoring existing adapters and tool registries.

## Copyright

Copyright 2026 Justin Cook
