# Design Strategy: ToolRegistry Context Parity (INFRA-145)

## 1. Objective
Ensure that both Console (TUI) and Voice interfaces consume tools through a unified `ToolRegistry` while supporting interface-specific `RunnableConfig` injection to maintain parity and satisfy ADR-029.

## 2. Context Injection Strategy

**Problem Statement**
Voice tools often require `RunnableConfig` injection (specifically `configurable` fields) to handle streaming audio events, state management, and callback routing. The current `ToolRegistry` returns static tool instances which lacks a unified way to inject this context at runtime.

**Proposed Strategy: Runtime Binding**
- **Stateless Registry**: The `ToolRegistry` will remain a stateless singleton that manages tool discovery and metadata.
- **Interface-Specific Config**: 
    - **Console Interface**: Will pass its `RunnableConfig` (telemetry, user context) to the `AgentSession`.
    - **Voice Interface**: Will pass its `RunnableConfig` (voice event loop, TTS buffers) to the `VoiceOrchestrator`.
- **Dynamic Binding**: The `Executor` (`agent/core/engine/executor.py`) will be the central point where the interface-provided `RunnableConfig` is bound to the tool instance retrieved from the registry. This will use the standard ADK/LangChain `.with_config()` or manual context injection pattern to ensure parity.

## 3. ADR-029 Alignment
ADR-029 specifies a multi-agent architecture where interfaces are thin adapters. By unifying tool lookup and execution under the `ToolRegistry` and a shared `Executor`, we ensure that:
1. Any new tool registered is immediately available to both Console and Voice.
2. Tool execution logic (including status yielding like 'Thinking...') is identical across interfaces.
3. Security and schema validation are applied consistently at the core layer.

## 4. Verification Strategy
- **AC-5 Integration Test**: A single test suite will verify that `ToolRegistry.list_tools()` returns an identical list of tool definitions when called from both the TUI session and the Voice orchestrator.
- **Negative Test**: Verify that removing a tool from the centralized registration point results in a `ToolNotFoundError` in both interfaces simultaneously.
