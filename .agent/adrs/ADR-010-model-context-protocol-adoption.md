# ADR-010: Model Context Protocol (MCP) Adoption

## Status

ACCEPTED

## Context

The agent needs a way to interact with external tools and services (specifically GitHub for reading repositories and managing issues) in a structured, programmable way.
Current options include:

1. **Shell CLI (`gh`)**: Brittle parsing of stdout, difficult to handle complex structured data.
2. **Proprietary Integrations**: GitHub Copilot "Agent Mode" provides this but requires a **Copilot Pro+ subscription ($39/mo/user)**, which is not cost-effective for all users.
3. **Custom API Clients**: Building bespoke clients (e.g., using `PyGithub`) requires significant maintenance and code duplication.

## Decision

We will adopt the **Model Context Protocol (MCP)** as the standard interface for agent-tool communication.
We will implement a native **MCP Client** within `agentic-dev` (`agent.core.mcp`) that can connect to compatible MCP servers.

The first implementation will target the **GitHub MCP Server** (`@modelcontextprotocol/server-github`) running locally via `npx` (stdio transport).

**Relationship to `gh` CLI & Workflow Flexibility**:

* **Choice & Interoperability**: Users and Workflows may utilize either `mcp` or `gh` based on preference and suitability. The architecture must support both coexisting and being used interchangeably where technically feasible.
* **Agent Preference**: While the Agent will default to **MCP** for reasoning tasks due to structured data, it must remain capable of utilizing `gh` if requested or if that is the user's preferred workflow tooling.
* **Workflow Agnosticism**: Future workflows should be designed to allow swapping the underlying execution tool (MCP vs CLI) to prevent vendor lock-in to a specific interface.

## Consequences

### Positive

* **Cost Savings**: Eliminates the need for Copilot Pro+ subscriptions for agentic GitHub capabilities.
* **Standardization**: Provides a uniform way to add future tools (Postgres, Slack, etc.) by just plugging in their MCP servers.
* **Reduced Maintenance**: We don't need to write/maintain a full GitHub API client; we just consume the standard server's tools.

### Negative

* **Dependency**: Requires `npx` (Node.js) to be available on the user's machine to run most standard MCP servers.
* **Complexity**: Adds a new protocol layer and dependency (`modelcontextprotocol`) to the agent core.
* **Latency**: Stdio communication with a subprocess may introduce slight overhead compared to direct in-process API calls (negligible for this use case).

## Compliance

* **Security**: Authentication tokens (PATs) must be injected safely into the MCP server process environment and managed via `agent secret`.
