# INFRA-041: Implement Voice Agent Process Streaming
## State

COMMITTED

## Problem Statement

The Voice Agent executes long-running operations (like `git status`, `npm install`, or `agent preflight`) but historically waited for them to complete before giving any feedback. This led to a "black box" user experience where the user didn't know if the agent was stuck or working. Additionally, there was no standard way to handle interactive processes (like a shell prompting for input) or ensure that subprocesses were cleaned up if the agent crashed.

## User Story

As a Developer using the Voice Agent, I want real-time streaming feedback from all tools and the ability to interact with shell processes, so that I can monitor progress, answer prompts, and trust that the agent is actively working on my request.

## Acceptance Criteria

- [x] **Process Lifecycle Management**: Implement a singleton `ProcessLifecycleManager` to track all spawned subprocesses and ensure they are killed on exit.
  - [x] Support ID-based retrieval of running processes.
- [x] **Real-Time Streaming**: Refactor core tools (`shell_command`, `git`, `preflight`) to stream `stdout`/`stderr` line-by-line to the `EventBus`.
  - [x] Output must appear in the frontend "Terminal" console.
- [x] **Interactive Shell**: specific tools (`start_interactive_shell`, `send_shell_input`) to allow starting detached processes and sending input to them later.
- [x] **Standardization**: Create an ADR (`ADR-013`) to mandate these patterns for future tools.
- [x] **Fix Regressions**: Ensure JSON output is compatible with the frontend (fixed `[object Object]` bug).

## Non-Functional Requirements

- **Latency**: Output logs should appear in the UI with minimal delay (<100ms).
- **Reliability**: No zombie processes left behind after agent restart.
- **Safety**: Interactive shell must not allow breaking out of the user's permission scope (inherits user context).

## Linked ADRs

- [ADR-013-voice-agent-streaming-and-process-management.md](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-013-voice-agent-streaming-and-process-management.md)

## Impact Analysis Summary

Components touched: `backend/voice/process_manager.py`, `backend/voice/tools/qa.py`, `backend/voice/tools/git.py`, `backend/voice/tools/interactive_shell.py`, `backend/voice/orchestrator.py`.
Workflows affected: Tool execution, Console interaction.
Risks identified: Potential for event loop congestion if streaming is too verbose (mitigated by `call_soon_threadsafe`).

## Test Strategy

### Unit Tests (>80% Coverage)
- **Wait/Process Management**:
  - `ProcessLifecycleManager`: Verify registration, retrieval, and kill_all (cleanup).
  - `EventBus`: Verify topic subscription, publishing, and thread safety (concurrent access).
- **Tools**:
  - `interactive_shell`: Verify `start_interactive_shell` spawns process and registers ID.
  - `send_shell_input`: Verify input is written to stdin.
  - `fix_story`: Verify AI prompt monitoring and fallback.
  - `workflows`: Verify wrapper functions correctly delegate commands.
- **Integration**:
  - `git`: Verify status/diff commands stream output to EventBus.
  - `onboard`: Verify `npm audit` streams output.

### E2E Tests (Playwright/Maestro)
- **Critical Flow 1: Interactive Shell**
  - Start standard shell command (`ls -la`).
  - Verify output appears in UI terminal.
  - Verify process exits cleanly.
- **Critical Flow 2: Long-Running Process**
  - Start a blocking process (e.g. `sleep 2`).
  - Verify UI shows busy state/streaming.
  - Verify process is tracked in lifecycle manager.
- **Critical Flow 3: Error Handling**
  - Start invalid command.
  - Verify error message streams to UI.
- **Critical Flow 4: Concurrency**
  - Start multiple shell sessions.
  - Verify output is routed to correct session IDs.

## Rollback Plan

- Remove `ProcessLifecycleManager` integration from tools.
- Revert `orchestrator.py` to use `payload` key (though this breaks frontend).
- Delete `interactive_shell.py`.
