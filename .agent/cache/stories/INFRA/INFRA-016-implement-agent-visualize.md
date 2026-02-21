# INFRA-016: Implement Agent Visualize

## State
COMMITTED

## Problem Statement
The codebase and its governance artifacts (Stories, Plans, Runbooks) are growing in complexity. Developers and stakeholders struggle to form a mental model of the system's architecture and the relationships between active tasks. Text-based lists are insufficient for understanding the directed graphs of dependencies in both code and project management.

## User Story
As a developer, I want to run `env -u VIRTUAL_ENV uv run agent visualize` to generate diagrammatic views of the project status and architecture, so that I can quickly understand dependencies and identify bottlenecks or architectural violations.

## Acceptance Criteria
- [ ] **Dependency View**: `env -u VIRTUAL_ENV uv run agent visualize graph` generates a Mermaid flowchart showing the relationship between Plans -> Stories -> Runbooks.
- [ ] **Story Flow**: `env -u VIRTUAL_ENV uv run agent visualize flow <story-id>` generates a specific subgraph for a story, showing its parent plan, child runbook, and touched files.
- [ ] **Hyperlinks**: Nodes in the diagram include clickable links to the actual files in the repository (GitHub compatible).
- [ ] **Sanitization**: Node labels (e.g., Story Titles) are sanitized to remove special characters that break Mermaid syntax.
- [ ] **Output**: The command outputs the Mermaid syntax to stdout by default.
- [ ] **Interactive Mode** (Optional): A `--serve` or `--html` flag to render the diagram in a browser (localhost only).
- [ ] **Architecture View** (Experimental): `env -u VIRTUAL_ENV uv run agent visualize architecture` is scoped as a "Nice to Have" or strict MVP that only shows high-level directory modifications, avoiding complex AST parsing for now.

## Non-Functional Requirements
- **Performance**: Graph generation should take less than 5 seconds for moderate repos (up to 1000 nodes).
- **Security**: `--serve` must bind to localhost only. No secrets/content displayed in nodes, only metadata.
- **Usability**: The output format must be directly pasteable into these markdown artifacts.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/visualize.py` (new), `agent/core/graph.py` (new).
Workflows affected: Planning and Review (aiding understanding).
Risks identified: Mermaid syntax fragility (mitigated by Sanitization AC).

## Test Strategy
- **Unit Tests**:
    - Parsing logic: Use **static fixture files** (dummy plans/stories) to verify graph traversal, not the live repo.
    - Sanitization: Test with strings containing quotes, brackets, and emojis.
- **Integration Tests**:
    - Verify `env -u VIRTUAL_ENV uv run agent visualize --help` documentation.
    - Verify output validity (basic regex check for `graph TD` header).

## Rollback Plan
- Delete the command file.
