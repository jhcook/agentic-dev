# ADR-013: Voice Agent Real-Time Streaming and Process Management

## Status

COMMITTED

## Context

The Voice Agent needs to perform complex, long-running operations (e.g., `agent preflight`, `npm install`, interactive shell sessions) while providing immediate feedback to the user.

- **Latency**: Users cannot wait for a command to finish before seeing output; they need real-time streaming.
- **Interactivity**: Users may need to provide input to running processes.
- **Reliability**: Spawning subprocesses in a persistent agent process risks creating "zombies" (orphaned processes) if the agent crashes or restarts.
- **Thread Safety**: The Agent runs in an `asyncio` loop, but tools often run in threads (via LangChain's `run_in_executor`). This creates race conditions when emitting events.

## Decision

We will standardize the Voice Agent's execution model on three pillars:

### 1. Centralized Process Lifecycle Management
All subprocesses spawned by the agent MUST be registered with the singleton `ProcessLifecycleManager`.
- **Registry**: Processes are stored in a `dict[str, Popen]` mapping, allowing retrieval by ID.
- **Cleanup**: The manager uses `atexit` hooks and signal handlers to ensure all registered processes are terminated when the agent shuts down.
- **Interactive Access**: Tools can look up running processes by ID to send `stdin` (e.g., answering "yes" to a prompt).

### 2. EventBus-based Console Streaming
All tools must stream their `stdout` and `stderr` to the frontend via the `EventBus`.
- **Channel**: Use `EventBus.publish(session_id, "console", line)`.
- **Protocol**: The Orchestrator wraps these events in the JSON protocol: `("json", {"type": "console", "payload": "..."})`.
- **Thread Safety**: The Orchestrator uses `loop.call_soon_threadsafe` to ensure events emitted from background threads are safely queued on the main `asyncio` loop.

### 3. Interactive Shell Pattern
For interactive tasks, we adopt a "Start/Detach/Interact" pattern:
- **Start**: `start_interactive_shell` spawns a process, registers it, starts a background reader thread, and returns immediately with a `process_id`.
- **Interact**: `send_shell_input` uses the `process_id` to write to the process's `stdin`.

### 4. Strict Secrets Management
To verify strict compliance and prevent secret leakage:
- **No Env Var Fallback**: The Agent MUST NOT fall back to checking environment variables (e.g., `GEMINI_API_KEY`) if a secret is missing from the secure store.
- **Justification**: Environment variables are often leaked in logs or process listings. Secrets must remain encrypted at rest and in memory.

### 5. Thread Safety
The proper functioning of the `EventBus` in a threaded environment (e.g., `process_manager` threads) requires:
- **Locking**: The `EventBus` must use a `threading.RLock` to protect its subscriber list and publish mechanism.

## Consequences

### Positive
- **User Experience**: Users see logs instantly.
- **Safety**: No orphaned processes consuming system resources.
- **Consistency**: All tools behave the same way (git, preflight, shell).
- **Extensibility**: New tools just need to follow the `ProcessLifecycleManager` pattern to get these benefits for free.

### Negative
- **Complexity**: Tool implementation is slightly more complex (requires registering process, handling threads).
- **Statefulness**: The agent becomes stateful (holding open process handles), which complicates scaling (though the voice agent is currently single-instance per user).

## Compliance & Security
- **Isolation**: Processes run as the user, inheriting their permissions.
- **Audit**: All commands executed and their outputs are logged to the `EventBus`, creating an audit trail in the session logs.
- **Resource Limits**: The `ProcessLifecycleManager` prevents unlimited zombie accumulation.
