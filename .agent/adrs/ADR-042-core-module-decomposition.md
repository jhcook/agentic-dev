# ADR-042: Core Module Decomposition

## Status

Accepted

## Date

2026-03-12

## Context

Following the standards established in ADR-041 (Module Decomposition Standards), the `context.py` and `implement/orchestrator.py` modules were identified as exceeding or approaching the Line of Code (LOC) thresholds. These modules combined multiple, distinct responsibilities into monolithic files, making them harder to maintain, test, and understand.

Specifically:
- `context.py` handled loading global rules, agent definitions, architectural decision records (ADRs), source file trees, and source code snippets, as well as integrating with the Model Context Protocol (MCP).
- `orchestrator.py` handled the overall flow of runbook implementation, but also contained extensive logic for parsing runbook blocks (`[MODIFY]`, `[NEW]`, etc.) and resolving ambiguous or relative file paths.

To adhere to the single-responsibility principle and stay within the 500-LOC warning threshold and 1,000-LOC hard ceiling, these modules needed to be decomposed.

## Decision

We are explicitly establishing new, documented module boundaries for the core context loading and implementation orchestration subsystems.

### 1. `ContextLoader` Decomposition

The responsibilities of `context.py` are explicitly split into functional domains:
- **`core/context_docs.py`**: Extracts the responsibility of loading documentation-related context. This includes parsing Architectural Decision Records (ADRs), Test Impact Matrices, and Behavioral Contracts.
- **`core/context_source.py`**: Extracts the responsibility of loading source-code-related context. This includes generating the `SOURCE FILE TREE` and extracting `SOURCE CODE OUTLINES` (imports and function signatures) within established token budgets.
- **`core/context.py`**: Retains the `ContextLoader` class as a facade and orchestrator. It continues to load global rules and agent definitions, and it orchestrates the calls to `context_docs.py` and `context_source.py` to build the final context payload. It also retains the `MCPClient` and vector database integration.

### 2. `Orchestrator` Decomposition

The responsibilities of `implement/orchestrator.py` are explicitly separated logically:
- **`core/implement/parser.py`**: Extracts all parsing logic for interpreting the runbook markdown format. This module is solely responsible for extracting `[MODIFY]`, `[NEW]`, and `[DELETE]` blocks and identifying the target files and structural contents.
- **`core/implement/resolver.py`**: Extracts all path resolution logic. This module is responsible for taking a possibly ambiguous, partial, or relative path from a runbook block and deterministically resolving it to an absolute path within the workspace, employing fuzzy matching and explicit path correction heuristics.
- **`core/implement/orchestrator.py`**: Retains the `Orchestrator` class. Its role is strictly to manage the state machine and side-effects of implementing a runbook (e.g., iterating over blocks, executing file writes, tracking cumulative lines of code modified, and invoking the AI service for complex refactors).

## Consequences

### Positive
- Modules are now strictly focused on single responsibilities.
- The LOC count for `context.py` and `orchestrator.py` is dramatically reduced, removing `agent preflight` governance blockers.
- Unit tests can focus entirely on one aspect (e.g., path resolution vs string parsing) without mocking entire orchestration logic.

### Negative
- Increases the number of files and imports across the `core` package.
- Requires updates to consumer integration tests to mock the new, narrowly-scoped functions rather than the monolithic classes.

## Related

- **ADR-041**: Module Decomposition Standards (motivates this ADR)
- **INFRA-123**: Core Context and Orchestrator Refactor

## Copyright

Copyright 2026 Justin Cook
