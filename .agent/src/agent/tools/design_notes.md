# Architecture Design: Search & Git Modules (INFRA-142)

## 1. AST-Aware Lookup
For Python files, the `find_symbol` tool parses code into an Abstract Syntax Tree using the Python standard library `ast` module. This allows for semantic identification of class and function boundaries, providing accurate line-level context to the agent.

## 2. Performance Requirements
To ensure performance NFRs are met:
- **Lazy Parsing**: No repository-wide indexing is performed. Parsing occurs only for identified candidate files during the execution of a tool call.
- **Pre-filtering**: Standard OS directory walking and filename extension checks are used to eliminate non-target files before invoking the AST parser.

## 3. Registry Integration
Tools are registered via `ToolRegistry.register()`. All handlers use the lambda pattern to capture the `repo_root` dependency at registration time, maintaining a clean interface for the agentic loop.