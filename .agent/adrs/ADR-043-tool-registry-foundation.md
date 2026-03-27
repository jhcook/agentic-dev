# ADR-043: Tool Registry Foundation

## Status

Accepted

## Date

2026-03-14

## Context

As the agent tool surface grew across stories INFRA-139 through INFRA-144, tool definitions were scattered between `core/adk/tools.py`, inline closures, and ad-hoc registration calls. This caused several problems:

- No single canonical registry — tool lookup required scanning multiple modules.
- Adding a new tool domain (e.g., search, git) required editing `make_tools()` directly, violating the open/closed principle.
- Security controls (path validation, PII scrubbing, shell sanitization) were re-implemented per-tool with no shared enforcement layer.
- ADK panel agents loaded tools by convention rather than contract, making it easy to ship an agent without a required tool.

A unified registry is needed so that domain modules self-register, security primitives are applied once at the boundary, and the ADK panel always receives a verified, complete tool set.

## Decision

We establish `agent/tools/` as the canonical tool registry package with the following structure:

### 1. `agent/tools/__init__.py` — Registry Root

- Exposes `ToolRegistry` as the global registry singleton.
- Provides `register_domain_tools(registry, repo_root)` which iterates registered domain modules and calls their `register()` function.
- Security primitives (`_validate_path`, `_sanitize_query`) live here as shared utilities imported by all domain modules.

### 2. Domain Modules (`search.py`, `git.py`, …)

- Each domain module exposes a `register(registry, repo_root)` function.
- Tools within a domain are plain Python functions with full type annotations and docstrings (for ADK schema inference).
- All filesystem access must call `_validate_path` from the registry root — no raw `Path` operations.
- `shell=False` is mandatory in all `subprocess` calls; `shell=True` is explicitly forbidden.

### 3. AST-Aware Search (`search.py`)

- `find_symbol` uses a two-stage approach: ripgrep pre-filter followed by `ast.parse` validation to ensure semantic accuracy.
- `search_codebase` caps results at 50 matches with PII scrubbing applied before returning to the LLM.

### 4. Structured Git Operations (`git.py`)

- `blame` and `file_history` use `subprocess` with `shell=False` and list-form arguments.
- All git refs are sanitized via `_sanitize_git_ref` before being passed to subprocess.
- Commit messages are sanitized via `_sanitize_commit_message` to prevent null-byte injection.

## Consequences

### Positive

- Single registration point — new tool domains are added by dropping a module into `agent/tools/` and calling `register()`.
- Security primitives applied once at the boundary, not per-tool.
- ADK panel always receives the complete, verified tool set via `register_domain_tools`.
- Testable in isolation — domain modules can be unit-tested without standing up the full ADK stack.

### Negative

- `register_domain_tools` will grow as more domains are added; periodic decomposition (per ADR-041 thresholds) will be required.
- Existing callers of `make_tools()` in `core/adk/tools.py` must migrate to the registry; a compatibility shim is maintained during transition.

## Related

- **ADR-040**: Agentic Tool Calling Loop (motivates this ADR's scope)
- **ADR-041**: Module Decomposition Standards (LOC thresholds apply to domain modules)
- **ADR-042**: Core Module Decomposition (established `core/implement/` boundary pattern)
- **INFRA-139**: Core Tool Registry and Foundation
- **INFRA-142**: Search and Git Module Migration

## Copyright

Copyright 2026 Justin Cook
