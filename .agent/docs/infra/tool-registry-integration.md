# Unified Tool Registry Integration Guide

## Overview

INFRA-145 introduces a unified approach to tool management. Previously, the Console (TUI) and Voice interfaces independently discovered and instantiated tools, leading to logic duplication and feature drift. Both interfaces now act as thin adapters over a centralized `ToolRegistry`.

## Architecture

**Central Registry**
The `ToolRegistry` (defined in `agent/core/adk/tools.py`) is the single source of truth for all tools available to the agent. It handles discovery, instantiation, and schema validation.

**Interface Adapters**
- **Console TUI**: The TUI session manager (`agent/tui/session.py`) initializes the registry and provides it to the underlying `AgentSession`.
- **Voice Orchestrator**: The voice logic (`backend/voice/orchestrator.py`) utilizes the same registry to resolve tool calls, ensuring that voice capabilities mirror console capabilities exactly.

## Developer Workflow

**Registering a New Tool**
1. **Implement**: Create your tool class in `agent/tools/` extending `BaseTool`.
2. **Register**: The registry uses automated discovery. Ensure your tool is included in the package search paths defined in the registry configuration.
3. **Verify**: Use the parity test suite (`pytest .agent/tests/integration/test_tool_parity.py`) to confirm the tool is correctly exposed to both interfaces.

**Contextual Configuration**
Voice-specific context is passed through `RunnableConfig`. The registry lookup mechanism supports passing this configuration into the tool instances to maintain session state across execution boundaries.

## Interface Parity (AC-5)

The system enforces that `ToolRegistry.list_tools()` returns identical results regardless of which interface calls it. This parity is crucial for maintaining a unified user experience across text and voice. Integration tests verify that removing a tool from the registry makes it unavailable in both interfaces simultaneously.

## Observability

The unified registry integrates with OpenTelemetry to provide a single trace path for tool execution. This ensures that latency and error rates for specific tools can be audited globally, regardless of the initiating interface.

## Troubleshooting

| Issue | Possible Cause | Resolution |
|---|---|---|
| Tool not found in Voice | Registry exclusion | Ensure the `backend/voice/orchestrator.py` is correctly initializing the registry with the required toolsets. |
| Blocked interface during tool execution | Synchronous tool implementation | The `executor.py` has been refactored to yield 'Thinking...' status updates. If the interface still blocks, verify the tool implementation is truly asynchronous. |
| Schema Mismatch | Invalid `args_schema` | The registry strictly validates schemas against the LLM's expectations. Use `BaseTool.args_schema` to define complex input structures. |
