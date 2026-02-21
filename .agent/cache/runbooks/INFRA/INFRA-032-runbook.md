# STORY-ID: INFRA-032: Implement GitHub MCP Client Support

## State

ACCEPTED

## Goal Description

Develop a cost-effective integration for GitHub repository, issue, and pull request management by implementing a GitHub MCP (Model Context Protocol) client in the `agent` software. Leverage the user's existing Personal Access Token (PAT) without requiring an expensive GitHub Copilot Pro+ subscription. Ensure secure secret management, robust error handling, and compatibility with the `npx` runtime.

## Panel Review Findings

### **@Architect**

- No significant architectural risks identified. The introduction of `agent.core.mcp.MCPClient` aligns with the modular design principles of the existing architecture.
- Noted dependency on `npx` could be a limitation for users without Node.js installed. Potential to include error handling or fallback mechanisms to guide such users.
- Clear considerations taken with respect to extensibility for other MCP-based functionality. The structure appears future-compatible with other MCP servers.
- Proposal aligns with current ADR standards; no deviations found. If new architectural decisions are made during the implementation (e.g., significant rearchitecting), a new ADR should be submitted per governance rules.

### **@Security**

- Emphasis on securely storing the GitHub PAT is appropriate and consistent with security practices. However:
  - Detailed validation of the PAT's format is required to minimize client misuse or misconfiguration.
  - Ensure that all logs redact sensitive token information using `env -u VIRTUAL_ENV uv run agent secret`.
  - No formal plan is outlined to secure or isolate the `npx` execution environment. Node.js package manager environments may pose security risks if not controlled (e.g., malicious/compromised server components).
- Consider TLS/SSL validation for all MCP-related requests if applicable.

### **@QA**

- While the high-level acceptance criteria for tasks are defined, more detailed test cases should be enumerated in the Implementation Steps and Verification Plan.
- Ensure robust coverage for edge cases, such as connection drops to the MCP server, invalid tokens, and malformed JSON responses.

### **@Docs**

- User perspective is missing regarding how to properly use the new CLI commands. Examples for `env -u VIRTUAL_ENV uv run agent mcp start` and `env -u VIRTUAL_ENV uv run agent mcp run` commands should be included in `README.md`.
- New onboarding scenarios (choosing between `mcp` and `gh`) should be clearly highlighted in documentation.
- Update documentation to clarify that `agent` now supports an alternative to `gh`.
- Guidelines should be given for setting up Node.js and `npx` if the user does not have them installed.

### **@Compliance**

- No formal linkage to ADR standards observed. Any major changes or deviations in architectural principles identified during implementation should result in a new ADR being published or updated per governance rule `adr-standards.mdc`.
- Ensure alignment of GitHub API interactions with rule `api-contract-validation.mdc`. If API interactions introduce schema changes that may be reusable, a corresponding OpenAPI definition must be maintained.

### **@Observability**

- Limited visibility in the current proposal for observability specifics:
  - Logs should include detailed contextual information when MCP operations are initiated/completed (e.g., `agent.mcp.start` with server identifier details).
  - Include telemetry to capture metrics such as the count of successful/failed command executions, connection stability, and response times for MCP-based GitHub operations.
- Ensure to mask sensitive inputs (e.g., tokens) in logs and telemetry output.

## Implementation Steps

### `agent/core/mcp/client.py`

#### NEW `agent/core/mcp/client.py`

- Define `MCPClient` with methods for:
  - Initializing connection to the MCP server.
  - Handling stdio-based communication with the server.
  - Sending commands to the server (e.g., `list_repositories`, `create_issue`, etc.).
  - Gracefully handling and retrying connection drops.
- Example for `MCPClient` initialization:

```python
class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.connection = None

    def connect(self):
        # Establish stdio connection to MCP server
        pass

    def send_command(self, command: str, payload: dict):
        # Send command along stdio and retrieve output
        pass

    def close_connection(self):
        # Gracefully close the connection
        pass
```

### `agent/commands/mcp.py`

#### NEW `agent/commands/mcp.py`

- Add CLI subcommands:
  - `start`: Start an interactive MCP session. Pass user-provided server arguments to `MCPClient.init` and maintain the connection to listen for user commands.
  - `run`: Execute a single command against an MCP server, print results, and exit.

### `pyproject.toml`

#### MODIFY `pyproject.toml`

- Add dependency: `modelcontextprotocol==<latest_version>`.

### `agent/core/mcp/__init__.py`

#### NEW `agent/core/mcp/__init__.py`

- Import and expose the `MCPClient` for other `agent` modules.

### `agent/config.py`

#### MODIFY `agent/config.py`

- Add a default configuration for the `github` server. Example:

```python
DEFAULT_CONFIG = {
    ...
    "github": {
        "server_cmd": "npx -y @modelcontextprotocol/server-github"
    }
}
```

### `tests/test_mcp_client.py`

#### NEW `tests/test_mcp_client.py`

- Create unit tests for:
  - Connection establishment and error handling (`MCPClient.connect`).
  - Simulate server responses and validate `MCPClient.send_command`.
  - Token validation (ensure incorrect tokens raise appropriate exceptions).

### `agent/commands/onboard.py`

#### MODIFY `agent/commands/onboard.py`

- Add onboarding step to configure `mcp` vs `gh`.
  - If `mcp` is selected, prompt for GitHub PAT and store it using `env -u VIRTUAL_ENV uv run agent secret`.

### Documentation

#### NEW `docs/mcp_integration.md`

- Document:
  - Example GitHub MCP use cases.
  - CLI command examples and outputs for `env -u VIRTUAL_ENV uv run agent mcp start` and `env -u VIRTUAL_ENV uv run agent mcp run`.
  - Setting up secrets and integration (PAT guidance).

#### MODIFY `README.md`

- Add summary of MCP integration and benefits over `gh` CLI.

## Verification Plan

### Automated Tests

- [ ] Test `MCPClient` connection logic and failure handling.
- [ ] Test sending and receiving commands via `MCPClient`.

### Manual Verification

- [ ] Run `env -u VIRTUAL_ENV uv run agent mcp start github` to establish an interactive MCP session.
- [ ] Run `env -u VIRTUAL_ENV uv run agent mcp run github list_repositories` with valid/invalid tokens.
- [ ] Verify onboarding prompts and saved configuration for `mcp` settings.
- [ ] Verify E2E flow with `npx` server.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with MCP client addition.
- [ ] README.md updated with CLI command examples.
- [ ] New documentation file (`docs/mcp_integration.md`) prepared.

### Observability

- [ ] Logs redact sensitive personal access tokens (PAT).
- [ ] Metrics collected for:
  - Commands executed.
  - Connection success/failure ratios.
  - Response times.

### Testing

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Verified on developer environments.
