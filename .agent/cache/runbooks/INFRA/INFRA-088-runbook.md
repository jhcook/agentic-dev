# INFRA-088: Console Agentic Tool Capabilities

## State

ACCEPTED

## Goal Description

Enable the Terminal Console TUI to leverage agentic workflows, allowing for complex development tasks through tool usage and real-time feedback.

## Linked Journeys

- JRN-088: Console Agentic Tool Workflows
- INFRA-087: Terminal Console TUI

## Panel Review Findings

**@Architect**: The proposed changes involve significant modifications to the agentic loop and tool registry. We need to ensure that the new tool integrations are modular and don't introduce tight coupling with the console TUI. ADR-028 (Typer Synchronous CLI Architecture) should be considered when integrating command execution. We need to ensure proper context isolation.
**@Qa**: The Acceptance Criteria are well-defined, but the Test Strategy needs more specifics regarding security and performance testing, especially around command execution sandboxing and handling of large files.
**@Security**: The security risks associated with command execution require stringent controls. We need to ensure that all command executions are sandboxed and adhere to ADR-002 (Security Controls). Input sanitization and output scrubbing are critical. No secrets in the tool registry.
**@Product**: The user story is clear and addresses a significant need. The negative test case is important for a robust user experience. Need to ensure that error messages are user-friendly.
**@Observability**: Implement detailed logging and tracing for tool usage, command execution, and error handling using OpenTelemetry. We need to monitor resource consumption for each tool call.
**@Docs**: The new agentic tool capabilities must be clearly documented, including instructions on how to use the tools and troubleshoot common issues. Update README.md to include info on the console agent.
**@Compliance**: Ensure that all data handling complies with GDPR and other relevant regulations. Verify license headers are present in new code.
**@Mobile**: N/A - This story primarily affects the backend and console TUI, not the mobile app.
**@Web**: N/A - This story does not directly impact the web interface.
**@Backend**: The backend API needs to be extended to support tool execution and real-time output streaming. Type enforcement should be strictly followed. Ensure API documentation is updated.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert prints to logger in `src/agent/tui/commands.py` and `src/agent/tui/app.py`
- [ ] Standardize error handling in `src/agent/core/adk/tools.py` to provide more informative messages.
- [ ] Implement `EXC-003` to allow `shell=True` for agentic tools while maintaining sandbox boundaries.

## Implementation Steps

### `src/agent/core/adk/tools.py`

#### MODIFY `src/agent/core/adk/tools.py`
- Revert `run_command` to use `shell=True` and remove `.venv` pathing.
- Implement command string validation to prevent path traversal outside repo root.

```python
def run_command(command: str) -> Tuple[str, str]:
    """Runs a shell command and returns stdout and stderr."""
    # shell=True is enabled via EXC-003
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # ...
```

def find_files(pattern: str) -> List[str]:
    """Finds files matching the given pattern."""
    try:
        # Security: Limit the search scope to the repository.
        files = [str(f) for f in Path(".").rglob(pattern)]
        return files
    except Exception as e:
        return [f"Error finding files: {e}"]

def grep_search(pattern: str, filepath: str) -> str:
    """Searches for a pattern in a file using grep."""
    try:
        # Security: Validate filepath to prevent directory traversal attacks.
        if ".." in filepath:
            return "Error: Invalid filepath (directory traversal detected)."
        result = subprocess.run(
            ["grep", pattern, filepath],
            capture_output=True,
            text=True,
            check=False  # Don't raise an exception on non-zero exit codes.
        )
        return result.stdout
    except Exception as e:
        return f"Error during grep search: {e}"
```

#### MODIFY `src/agent/core/adk/tools.py`
- Add the above tool functions to the `__all__` list.

### `src/agent/core/adk/orchestrator.py`

#### MODIFY `src/agent/core/adk/orchestrator.py`

-  Integrate the new tool functions into the agentic loop. This involves making the tools available to the agent and handling the tool calls.
- Add try/except blocks with proper logging for all tool calls.
```python
# Example integration (Illustrative - may require adaptation)
from agent.core.logger import get_logger
from agent.core.adk import tools
logger = get_logger(__name__)

async def execute_tool(tool_name: str, arguments: dict) -> str:
    try:
        if tool_name == "read_file":
            filepath = arguments.get("filepath")
            result = tools.read_file(filepath)
            return result
        elif tool_name == "edit_file":
            filepath = arguments.get("filepath")
            content = arguments.get("content")
            result = tools.edit_file(filepath, content)
            return result
        elif tool_name == "run_command":
            command = arguments.get("command")
            cwd = arguments.get("cwd", ".") # default to current directory
            stdout, stderr = tools.run_command(command, cwd)
            return f"Stdout: {stdout}\nStderr: {stderr}"
        elif tool_name == "find_files":
            pattern = arguments.get("pattern")
            result = tools.find_files(pattern)
            return str(result)
        elif tool_name == "grep_search":
            pattern = arguments.get("pattern")
            filepath = arguments.get("filepath")
            result = tools.grep_search(pattern, filepath)
            return result
        else:
            return f"Error: Tool {tool_name} not found."
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return f"Error executing tool {tool_name}: {e}"
```

### `src/agent/tui/app.py`

#### MODIFY `src/agent/tui/app.py`

- Modify the console TUI to handle the real-time output from the `run_command` tool. Display `stdout` and `stderr` in the chat panel.
- Add support for graceful degradation when function calling is not available.
- Add message to indicate if tools are unavailable due to provider limitations.
```python
# Example (Illustrative - may require adaptation)
    def display_message(self, message: str):
        """Displays a message in the chat panel."""
        self.query_one(ChatPanel).add_message(message)
```

### `src/agent/core/ai/llm_service.py`

#### MODIFY `src/agent/core/ai/llm_service.py`
- Add provider check if it supports function calling
```python
    def supports_function_calling(self) -> bool:
        """
        Check if LLM Provider supports function calling,
        """
        if self.provider_name in ["openai", "gemini", "anthropic"]:
            return True
        return False
```

### `src/agent/commands/console.py`

#### MODIFY `src/agent/commands/console.py`
- Add logic to initiate the agent loop in the TUI.
- Display a message if the current provider does not support function calling.
```python
import typer
from rich.console import Console

app = typer.Typer()

@app.command()
def console():
    """Starts the agent console."""
    console = Console()
    from agent.core.ai.llm_service import LLMService
    llm_service = LLMService()

    if not llm_service.supports_function_calling():
        console.print("[bold red]Warning:[/bold red] The current LLM provider does not support function calling. Some features may be limited.")
    else:
        console.print("[bold green]Function calling is enabled.[/bold green]")

    from agent.tui.app import AgentConsoleApp
    app = AgentConsoleApp()
    app.run()
```

### `src/agent/commands/console.py`

#### MODIFY `src/agent/commands/console.py`
- Add `--model` typer option to override the default model for the selected provider
- Pass `model` through to `ConsoleApp(provider=provider, model=model)`

### `src/agent/tui/app.py`

#### MODIFY `src/agent/tui/app.py`
- Accept `model` parameter in `ConsoleApp.__init__`, store as `_initial_model`
- In `on_mount`, after provider setup, set `ai_service.models[provider] = model` if provided
- Display model override confirmation in system message

### `src/agent/tui/agentic.py`

#### MODIFY `src/agent/tui/agentic.py`
- Convert `_gemini_agentic_loop` from `generate_content` to `generate_content_stream`
  - Stream text chunks via `on_chunk` as they arrive
  - Accumulate `function_call` parts, execute after stream ends, loop
- Convert `_openai_agentic_loop` from blocking to `stream=True`
  - Parse SSE deltas for text content and tool call fragments
  - Accumulate tool call arguments from incremental JSON deltas by index
- Convert `_anthropic_agentic_loop` from `messages.create` to `messages.stream()`
  - Use `text_stream` for incremental text output
  - Use `get_final_message()` for tool-use block extraction

### `src/agent/tui/app.py`

#### MODIFY `src/agent/tui/app.py`
- Synchronize `ai_service` with `self._session` during `/switch` and `/history`.
- Clear session model when switching providers via `/provider` or picker.
- Persist model selection to session and `ai_service`.
- Restore `@work(thread=True)` for `_do_stream` to fix shutdown hangs and streaming errors.

### `src/agent/core/engine/executor.py` & `parser.py`

#### MODIFY `src/agent/core/engine/executor.py`
- Yield `thought` event ONLY after successful parsing.
- Filter out empty or redundant thoughts.

#### MODIFY `src/agent/core/engine/parser.py`
- Clean `AgentAction.log` of raw JSON and internal prefixes.
- Ensure `AgentFinish` returns cleaned output matching the log.

## Verification Plan

### Automated Tests

- [x] Test 1: Unit tests for tool sandboxing in `.agent/tests/core/adk/test_interactive_tools.py`.
- [x] Test 2: Integration tests for command dispatch in `.agent/tests/tui/test_app.py`.
- [x] Test 3: Agent executor event streaming in `.agent/tests/tui/test_streaming_agentic.py`.
- [x] Test 4: Agentic loop tool calls in `.agent/tests/tui/test_agentic_loop.py`.
- [x] Test 5: Stream service tests in `.agent/tests/tui/test_stream.py`.
- [x] Test 6: Model selector tests in `.agent/tests/tui/test_model_selector.py`.
- [x] Test 7: Session persistence tests in `.agent/tests/tui/test_session.py`.
- [x] Test 8: **Stream routing regression tests** in `.agent/tests/tui/test_stream_routing.py` — 10 tests covering:
  - Regular chat uses simple streaming (not agentic ReAct loop)
  - Workflow/role invocations use agentic streaming
  - Non-FC providers always use simple streaming
  - `use_tools` flag propagation through `_stream_response`
  - `use_tools` preserved for disconnect retry
  - Command history populated on submit
  - `/search` and `/tools` in BUILTIN_COMMANDS
  - `/search` documented in help text

### Manual Verification

- [x] Step 1: Start the console TUI and interact with the agent, prompting it to read a file using the `read_file` tool. Verify that the file content is displayed correctly.
- [x] Step 2: Start the console TUI and interact with the agent, prompting it to edit a file using the `edit_file` tool. Verify that the file is modified and saved correctly.
- [x] Step 3: Start the console TUI and interact with the agent, prompting it to run a command using the `run_command` tool. Verify that the command is executed, and the output is displayed in the chat panel.
- [x] Step 4: Start the console TUI and interact with the agent, prompting it to find files using the `find_files` tool. Verify that the relevant files are identified and displayed correctly.
- [x] Step 5: Start the console TUI and interact with the agent, prompting it to search in a file using the `grep_search` tool. Verify that the relevant files are identified and displayed correctly.
- [x] Step 6: Test with function-calling and non-function calling provider.
- [x] Step 7: Attempt directory traversal in `grep_search`. Verify that the tool prevents access outside the repository.
- [x] Step 8: Attempt running a command with `run_command` that modifies files outside the repository. Verify that the tool prevents this.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated with information on the new agentic tool capabilities and their usage in the console TUI.
- [x] API Documentation updated (if applicable)
- [x] Update docstrings and comments for all new code.

### Observability

- [x] Logs are structured and free of PII
- [x] Metrics added for tool usage, command execution duration, and error rates. OpenTelemetry tracing added for tool call flows.

### Testing

- [x] Unit tests passed
- [x] Integration tests passed

## Copyright

Copyright 2026 Justin Cook