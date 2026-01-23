# INFRA-034: Implement ReAct Agent Loop Engine

## State

COMMITTED

## Problem Statement

The current `AIService.complete()` method is valid for single-turn "Question -> Answer" interactions. However, to support `INFRA-033` (Council Tool Use), we need a robust **ReAct (Reason + Act)** loop. The agent needs to be able to "think", decide to call a tool, pause for execution, receive the output, and continue thinking, potentially for multiple turns.

## User Story

As an Agent Developer, I want a dedicated `AgentExecutor` or enhanced `AIService` that implements the ReAct loop pattern, so that higher-level features (like Councils) can simply pass a prompt and a set of tools, and get back a final result after the agent has autonomously explored the problem.

## Acceptance Criteria

- [ ] **State Management**: The loop must handle state (history/context) independently of the stateless `AIService`.
- [ ] **Architecture**: Implement as a distinct `AgentExecutor` (or similar) that consumes `AIService`.
- [ ] **Pluggable Parsers**: Separate "Parsing" logic from "Execution" logic. Implement an interface `ToolParser` to support:
  - Text-based parsing (Regex for `Action: ...`)
  - Native Function Calling (OpenAI/Gemini JSON schemas)
- [ ] **Output Sanitization**: Tool outputs must be sanitized (e.g., escaping XML tags) before being inserted back into the Prompt to prevent injection attacks.
- [ ] **Safety Limits**:
  - [ ] `max_steps`: Strict hard limit (e.g., 10) to prevent infinite loops.
  - [ ] `token_limits`: Strategy for "Observation Folding" (summarizing older tool outputs) to preserve context window.
- [ ] **Async/Await**: The loop must be fully async to handle non-blocking IO.

## Non-Functional Requirements

- Observability: Must log all tool usage to `agent.log`.
- Performance: Loop overhead should be <100ms per turn.

## Test Strategy

- **Replay Testing**: Use recorded conversation files (Replay Files) to test the Parser/Executor deterministically.
- **Mocking**: Mock `MCPClient` to verify execution flow without real side effects.
- **Edge Cases**: Validate handling of malformed JSON and empty tool outputs.
