# INFRA-034: Implement ReAct Agent Loop Engine

## State

COMMITTED

## Problem Statement

The current `AIService.complete()` method is valid for single-turn "Question -> Answer" interactions. However, to support `INFRA-033` (Council Tool Use), we need a robust **ReAct (Reason + Act)** loop. The agent needs to be able to "think", decide to call a tool, pause for execution, receive the output, and continue thinking, potentially for multiple turns.

## User Story

As an Agent Developer, I want a dedicated `AgentExecutor` or enhanced `AIService` that implements the ReAct loop pattern, so that higher-level features (like Councils) can simply pass a prompt and a set of tools, and get back a final result after the agent has autonomously explored the problem.

## Acceptance Criteria

- [ ] **Loop Logic**: Implement the "Thought -> Call -> Observation -> Thought" loop.
- [ ] **Parsing**: Robust parsing of tool calls from LLM output (supporting both native Function Calling where available, and XML/JSON-RPC style fallback for others if needed).
- [ ] **Tool Execution**: Integration with `agent.core.mcp.MCPClient` to actually execute the tools.
- [ ] **Safety Limits**:
  - [ ] `max_steps`: Prevent infinite loops (e.g., limit to 10 turns).
  - [ ] `token_limits`: Manage context window growth (trimming old observations if needed).
- [ ] **Observability**: Detailed logging of each "Step" in the loop (Thought, Tool, Result) for debugging.

## Non-Functional Requirements

- Observability: Must log all tool usage to `agent.log`.
- Performance: Loop overhead should be <100ms per turn.

## Test Strategy

- Unit test the parser with varied LLM output examples.
- Mock `MCPClient` to verify execution flow without real side effects.
