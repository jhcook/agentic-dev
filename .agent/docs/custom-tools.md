# System Tools & Security

The Voice Agent is equipped with powerful tools to interact with the repository. These tools are strictly governed to prevent abuse.

## Core Tools

### `read_file(path)`

- **Purpose**: Read file contents to understand codebase context.
- **Security**:
  - **Repository Lock**: Cannot read files outside the project root (`../../` is blocked).
  - **Audit**: Every read operation is traced via OpenTelemetry (`tool.read_file`).

### `write_file(path, content)`

- **Purpose**: Modify code or create new files.
- **Security**:
  - **Repository Lock**: Strict containment within project root.
  - **Sensitive File Protection**: Blocked from writing to `.env`, `.git/`, and governance secrets.
  - **Audit**: Content size and path are logged to OpenTelemetry (`tool.write_file`).

### `shell_command(command, cwd)`

- **Purpose**: Run build commands, tests, or package installers.
- **Security**:
  - **CWD Lock**: Working directory must be within project root.
  - **Audit**: Command string and exit code are traced (`tool.shell_command`).

## Governance & Auditing

All tool usage is recorded in the system traces. The Governance Council reviews these logs to ensure compliance with security policies.

### Metrics

- `voice_agent_tool_usage_total`: Counter for tool invocation.
- `voice_agent_tool_latency`: Histogram for execution time.

## Custom Tools

### `add_license.py`

- **Purpose**: Automatically adds the Apache 2.0 license header to source files.
- **Supported Languages**: Python, TypeScript, JavaScript, YAML, Shell, CSS.
- **Behavior**: Respects shebangs (e.g. `#!/bin/bash`) and inserts the header after them.

### `git_stage_changes(files)`

- **Purpose**: Stage specific files or all changes (`git add`).
- **Security**:
  - **Risk**: Low, standard git operation.
  - **Audit**: All actions logged.

### CORS Configuration

The backend uses a `PermissiveASGIMiddleware` for local development. This middleware reflects the `Origin` header to allow WebSocket connections from `localhost`. This is a known configuration for the agent's isolated local environment (Dev Mode).
