Copyright 2026 Justin Cook

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


# EXC-003: Shell Execution for Agentic Tools (run_command)

## Status

Accepted

## Challenged By

@Security (CISO), ADR-027, ADR-028

## Rule Reference

Traditional recommendation (and previous implementation) forced `shell=False` and list-style arguments to prevent command injection. 

## Affected Files

- `.agent/src/agent/core/adk/tools.py` — `run_command` tool implementation

## Original Requirement

The user explicitly requested reverting to `shell=True` to allow standard shell features like pipes (`|`), redirections (`>`), and environment variable expansions within agent-executed commands.

## Justification

While `shell=True` increases the attack surface for command injection, the Agent CLI implements several mitigating layers:

1. **Path Sandbox**: `run_command` validates that the command string does not contain path traversal patterns (e.g., `..`) and attempts to restrict execution within the repo root.
2. **String-based Blocklist**: ADR-027 establishes a blocklist of dangerous strings that are scanned before execution.
3. **Interactive Human-in-the-Loop**: All tool calls in the Agent Console require user approval (unless explicitly marked as safe), providing a final layer of manual verification before any shell command is executed.
4. **Environment Isolation**: The CLI removes implicit `.venv` pathing, relying on the user's active shell environment, which is more transparent and predictable.

### Scope

This exception applies specifically to the `run_command` tool in `agent.core.adk.tools`. 

## Conditions

Re-evaluate this exception if:

- The "Auto-run" feature for tool calls is enabled globally without granular safety checks.
- The CLI is deployed in a multi-tenant or non-interactive environment where human approval is bypassed.
- New high-risk command patterns are identified that escape current blocklist/sandbox checks.

## Consequences

- **Positive**: Restores full shell power (pipes, redirects) to the agent, significantly increasing its utility for developer tasks.
- **Positive**: Simplifies command execution by removing complex `shlex` splitting and `.venv` path management.
- **Negative**: Increases the risk of command injection if the AI generates a malicious string and the user approves it without careful reading.
- **Negative**: Requires maintainers to be more vigilant about the `run_command` sandbox implementation.