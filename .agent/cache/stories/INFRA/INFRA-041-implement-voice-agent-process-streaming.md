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
  - [ ] **Origin Checks:** Implement origin checks in the `EventBus.publish` method to ensure that only authorized components can publish messages. See details below.
  - [ ] **UI Error Handling**: Modify the frontend to display clear error messages received from the backend, especially those related to invalid `cwd` values or origin check failures. This includes displaying a prominent warning message in the UI terminal *before* the command is executed, stating something like: "Warning: The specified working directory is outside the project root. Command execution is potentially unsafe. Contact your administrator if you did not expect this."
- [x] **Interactive Shell**: specific tools (`start_interactive_shell`, `send_shell_input`) to allow starting detached processes and sending input to them later.
  - [ ] **User Warning**: Add a clear warning message to the UI before the user starts an interactive shell session, explaining the risks of executing arbitrary commands.
- [x] **Standardization**: Create an ADR (`ADR-013`) to mandate these patterns for future tools.
- [x] **Fix Regressions**: Ensure JSON output is compatible with the frontend (fixed `[object Object]` bug).
- [ ] **Command Sanitization**: Implement input validation and sanitization for the `command` arguments in `shell_command` and `start_interactive_shell` to prevent command injection attacks. Use a strict allow-list of allowed commands or a robust escaping mechanism (e.g., `shlex.quote` in Python).

## Non-Functional Requirements

- **Latency**: Output logs should appear in the UI with minimal delay (<100ms).
- **Reliability**: No zombie processes left behind after agent restart.
- **Safety**: Interactive shell must not allow breaking out of the user's permission scope (inherits user context).
  - The `cwd` (current working directory) parameter used in subprocess calls across various tools *must* validate that the `cwd` (current working directory) is within the project root.
  - A warning message must be displayed when a user attempts to specify an invalid `cwd`.
  - The agent configuration loads some config params from environment variables and these must be validated during `agent preflight`.

## Origin Checks Implementation Details

The `EventBus` is a central component for communication between backend tools and the frontend. The absence of origin checks means that any client (malicious or otherwise) could potentially publish messages to the bus. Implement origin checks within the `EventBus` to ensure that only authorized components can publish messages.

1. **Identify Authorized Publishers:** Determine which backend components are allowed to publish events (e.g., `ProcessLifecycleManager`, specific tool modules).
2. **Implement Origin Verification:** Modify the `EventBus.publish` method to verify that the caller is in the list of authorized publishers. This can be achieved using:
    - Explicit Origin Metadata: Require publishers to pass an explicit `origin` parameter to the `publish` method, which the `EventBus` then validates against an allowlist. *Preferred Method*: More explicit and maintainable.
3. **Default Deny:** If the origin cannot be verified, reject the message and log a security warning.

```python
# backend/voice/events.py

import logging
import inspect

logger = logging.getLogger(__name__)

class EventBus:
    _authorized_publishers = {
        "backend.voice.process_manager",
        "backend.voice.tools.git",
        "backend.voice.tools.qa",
        "backend.voice.tools.interactive_shell",
        "backend.voice.tools.workflows",
        "backend.voice.tools.project",
        "backend.voice.orchestrator",
        "backend.voice.tools.observability"
    }

    def publish(self, topic: str, message: dict, origin: str = None):
        """Publishes a message to the specified topic.

        Args:
            topic: The topic to publish the message to.
            message: The message to publish.
            origin: The origin of the message (e.g., module name).
        """

        # if origin is None:
        #     stack = inspect.stack()
        #     # Get the frame of the caller (the function calling publish)
        #     frame = stack[1]
        #     origin = frame.filename
        #
        # if origin not in self._authorized_publishers:
        #     logger.warning(f"Unauthorized event publisher: {origin}. Message blocked.")
        #     return  # Block the message

        # Implementation to publish the message
        # ...
```

**Note:** The above implementation uses a simplified string comparison for the origin. For more robust verification, consider using module objects or other unique identifiers. If `inspect.stack()` is used, handle potential exceptions and ensure it doesn't introduce performance bottlenecks. Add logging to record the source of all messages published to the `EventBus` and add metrics to track the number of authorized and unauthorized requests to the `EventBus.publish` endpoint. This will help to detect and respond to potential attacks.

## Command Execution Origin Validation Details

The `run_pr` tool in `git.py` looks suspicious. It sets `shell=True` and `executable='/bin/zsh'`, suggesting it's executing arbitrary shell commands. However, it *doesn't* have the same `cwd` checks as `shell_command`. This is a potential **SECURITY RISK**.

- Add a `cwd=str(agent_config.repo_root)` parameter to `subprocess.Popen` call in `run_pr`.
- Add similar input validation to prevent directory traversal, as done in `shell_command`. This could be done by adapting the `_is_safe_path` function to ensure the commands executed by run_pr do not leave the repository.
- Add tests to verify the command runs in the root and cannot break out.

```python
import os
import subprocess
from pathlib import Path
from backend.voice.events import EventBus
from agent.core.config import config as agent_config
from langchain_core.runnables import RunnableConfig
import logging

logger = logging.getLogger(__name__)

def shell_command(command: str, cwd: str = ".", config: RunnableConfig = None) -> str:
    """Executes a shell command within a specified working directory."""
    thread_id = config.get("configurable", {}).get("thread_id", "default_thread")
    try:
        # Resolve the cwd to its absolute, canonical form
        project_root = Path(agent_config.repo_root).resolve()
        if cwd == ".":
            target_cwd = project_root
        else:
            target_cwd = (project_root / cwd).resolve()

        # Security: Verify that the target_cwd is a subdirectory of the project root
        try:
            target_cwd.relative_to(project_root)  # Raises ValueError if not a subdirectory
        except ValueError:
            error_message = f"Error: Working directory '{cwd}' is outside the allowed project scope.  Please specify a directory within your repository."
            EventBus.publish(topic=f"agent.message.{thread_id}", message=error_message)
            logger.warning(error_message)
            return error_message

        final_command = command
        logger.info(f"Executing command: {final_command} in {target_cwd}")

        # ... (Rest of the code remains the same, but use target_cwd)
        process = subprocess.Popen(
            final_command,
            shell=True,
            executable='/bin/zsh',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(target_cwd) # IMPORTANT: Use the validated target_cwd
        )
        # ...
```

If the `cwd` is invalid, *do not* silently fail. Instead, raise an exception with a clear, user-facing error message explaining why the directory is not allowed. This message must appear in the UI terminal (via the `EventBus`). Example:  `"Error: Working directory '{}' is outside the allowed project scope.  Please specify a directory within your repository."`. Also, add logging at the beginning of each tool function to record the command being executed, the `cwd`, and any relevant arguments.

## CLI Configuration

Add `--cwd` or `--project-dir` to the agent CLI itself, which the voice commands can optionally set. If CWD is configurable on the command line, the `agent preflight` needs to validate that CWD is in the valid range.

## Linked ADRs

- [ADR-013-voice-agent-streaming-and-process-management.md](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-013-voice-agent-streaming-and-process-management.md)
- Ensure that all environment variables used for configuration are checked by `agent preflight` and add documentation so the user can be sure that the Agent is correctly configured. Also, harden the preflight checks.

## Impact Analysis Summary

Components touched: `backend/voice/process_manager.py`, `backend/voice/tools/qa.py`, `backend/voice/tools/git.py`, `backend/voice/tools/interactive_shell.py`, `backend/voice/orchestrator.py`, `backend/voice/events.py`.
Workflows affected: Tool execution, Console interaction.
Risks identified: Potential for event loop congestion if streaming is too verbose (mitigated by `call_soon_threadsafe`), potential for command injection vulnerabilities, potential for unauthorized access to the event bus.

## Test Strategy

### Unit Tests (>80% Coverage)

- **Wait/Process Management**:
  - `ProcessLifecycleManager`: Verify registration, retrieval, and kill_all (cleanup).
  - `EventBus`: Verify topic subscription, publishing, and thread safety (concurrent access). Add tests to confirm that `EventBus.publish` rejects requests from unauthorized sources. Implement fuzzing or property-based testing to ensure that the system is resilient to malicious or malformed input on the event stream.
- **Tools**:
  - `interactive_shell`: Verify `start_interactive_shell` spawns process and registers ID.
  - `send_shell_input`: Verify input is written to stdin.
  - `fix_story`: Verify AI prompt monitoring and fallback.
  - `workflows`: Verify wrapper functions correctly delegate commands.
  - `shell_command`: Add tests that the tool returns an error message and *does not* execute the command when an invalid `cwd` is provided.
  - Create tests to validate `get_recent_logs`.
  - Add unit tests to specifically check if subprocess calls are invoked with `cwd`.
  - Add a set of new unit tests in `tests/voice/test_tools_cwd.py` to enforce that the `cwd` parameter is correctly passed to `subprocess.run` and `subprocess.Popen` in the relevant tools (`git.py`, `interactive_shell.py`, `qa.py`, `workflows.py`). These tests should mock the `agent_config` and `subprocess` modules to verify the `cwd` argument.
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
- **Security Tests:**
  - Attempt to use `".."` to escape the project root.
  - Attempt to use absolute paths pointing outside the project root.
  - Verify that the tool returns an error message and *does not* execute the command when an invalid `cwd` is provided.
  - Verify that the UI warning message is displayed.
  - Run `scripts/generate_openapi.py` to check for inconsistencies in endpoints, request models and response models.

## Rollback Plan

- Remove `ProcessLifecycleManager` integration from tools.
- Revert `orchestrator.py` to use `payload` key (though this breaks frontend).
- Delete `interactive_shell.py`.
- Remove origin checks and UI warning messages.
