# INFRA-034: Implement ReAct Agent Loop Engine

## State

ACCEPTED

## Goal Description

Build a robust, stateful `AgentExecutor` engine that enables "ReAct" (Reason + Act) loops. This decouples the agent's cognitive cycle (Thinking -> Tool Call -> Observation) from the stateless `AIService`. It provides the foundational "Brain" needed for Council agents to using tools securely and effectively.

## Panel Review Findings

(Verified via simulated panel consultation - see chat history)

### Key Decisions

1. **Decoupling**: `AgentExecutor` wraps `AIService`, not modifies it.
2. **Pluggable Parsing**: Support interface-based parsing to handle both Regex (Stubborn LLMs) and Native Tool Calls (Smart LLMs).
3. **Safety**: Hard `max_steps` limit and `SecureManager` scrubbing are mandatory.

## Implementation Steps

### 1. Core Structures (`agent.core.engine`)

#### [NEW] `agent/core/engine/typedefs.py`

- Define `AgentStep`, `AgentAction`, `AgentObservation` dataclasses.

#### [NEW] `agent/core/engine/parser.py`

- Define `BaseParser` interface.
- Implement `ReActJsonParser` (or RegexParser) as default.

#### [NEW] `agent/core/engine/executor.py`

- Implement `class AgentExecutor`:
  - `__init__(llm: AIService, tools: List[Tool], parser: BaseParser)`
  - `async def run(prompt: str) -> str`:
    - Initialize `history`.
    - `while steps < max_steps`:
      - Construct prompt with history.
      - Call LLM.
      - Parse output -> `AgentAction` or `AgentFinish`.
      - If Finish -> Return text.
      - If Action -> Call Tool (via MCPClient).
      - **CRITICAL**: Scrub Observation with `SecureManager`.
      - Append `(Action, Observation)` to history.
    - Raise `MaxStepsExceeded`.

### 2. Integration

#### [MODIFY] `agent/core/ai/service.py`

- Ensure `complete` (or a helper) allows raw message history injection if needed by the Executor (or Executor manages string concatenation for now to support non-chat models).

## Verification Plan

### Automated Tests

- [ ] **Unit**: `tests/core/engine/test_parser.py`: Feed sample LLM outputs (valid/invalid JSON, text) and verify correct `AgentAction` parsing.
- [ ] **Unit**: `tests/core/engine/test_executor.py`: Mock `AIService` and `MCPClient`. Verify loop runs N times and stops. Verify `max_steps` raises error.
- [ ] **Replay**: `tests/core/engine/test_replays.py`: Load a `.json` replay of a conversation and assert the Executor produces the expected "next step" given the history.

### Manual Verification

- [ ] Create a script `scripts/test_agent_loop.py` that instantiates an Executor with a dummy tool (e.g., `echo`).
- [ ] Run it and watch the logs: "Thinking... Calling Echo... Observing... Thinking... Final Answer".
