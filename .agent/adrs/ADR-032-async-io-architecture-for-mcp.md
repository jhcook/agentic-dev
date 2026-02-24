# ADR-032: Async I/O Architecture for MCP

## Status
Accepted

## Context
As the agent integrates with more complex tools via the Model Context Protocol (MCP), particularly slow I/O processes like full NotebookLM syncs, synchronous blocking calls in the CLI led to poor UX and timeouts. We need a way to support parallel tool invocation and background polling without locking the main thread.

## Decision
We will adopt an `async`-first architecture for I/O-bound operations across MCP and Contextual loading. Components like `mcp.py`, `context.py`, and `sync/notebooklm.py` will use `asyncio` for internal orchestration. Fast, CPU-bound operations and Typer CLI entry points will remain synchronous but will use `asyncio.run()` to dispatch to the async core.

## Consequences
- **Positive:** Improved throughput for heavy external integrations (e.g. MCP clients).
- **Positive:** Enables background processing and real-time streaming for future features like Voice interactions.
- **Negative:** Increased codebase complexity as developers must be aware of the boundary between `async` internal logic and `sync` Typer CLI methods.

## Copyright

Copyright 2024-2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
