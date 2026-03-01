# ADR-040: Agentic Tool-Calling Loop Architecture

## Status

Accepted

## Date

2026-02-27 (Updated 2026-03-01)

## Context

INFRA-088 introduces interactive tool-calling capabilities to the Agent Console
TUI. The AI can now read/write files, run commands, and search code within the
repository during a conversation. This requires an iterative loop that detects
tool-call requests from the AI, executes them safely, and feeds results back.

## Decision

### Overall Design

An iterative **agentic loop** (`agentic.py`) manages the tool-calling cycle:
1. Send user prompt + tool schemas to the AI provider
2. Inspect the response for function-call requests
3. Execute requested tools via a dispatch map
4. Feed tool results back to the AI
5. Repeat until the AI returns a final text response (max 10 iterations)

### Tool Registration & Schemas

- **Read-only tools** (`make_tools()`): `read_file`, `search_codebase`,
  `list_directory` — existing governance tools
- **Interactive tools** (`make_interactive_tools()`): `edit_file`,
  `run_command`, `find_files`, `grep_search` — new write/execute tools
- All tools are registered as JSON schemas (`TOOL_SCHEMAS[]`) for provider APIs
- A dispatch map (`_build_tool_dispatch()`) maps tool names → Python callables

### Provider Implementations

Each provider uses its native function-calling protocol:

| Provider | Implementation | Tool Format |
|----------|---------------|-------------|
| Gemini / Vertex | `types.FunctionDeclaration` | `google.genai.types` |
| OpenAI | Chat Completions `tools[]` | OpenAI function schema |
| Anthropic | Messages API `tools[]` | `input_schema` format |
| GH CLI / Ollama | Plain completion fallback | N/A |

### Security Sandboxing (`run_command`)

- Commands execute with `shell=True` to support pipes, redirections, and standard shell behavior.
- `cwd` locked to repository root.
- Path traversal (`..`) blocked in the command string.
- Absolute paths outside repository root (excluding known safe systemic paths) are rejected via regex validation.
- 120-second timeout enforced.
- Path validation (`_validate_path`) for file tools.
- Implicit `.venv` pathing is removed; the command runs in the user's active environment.

### Data Processing Consent

File contents and command outputs are sent to the configured AI provider.
Users are informed via the welcome message, which explicitly states that
tool results are transmitted to external AI providers for processing.

## Consequences

- AI can autonomously explore and modify code within the repository
- Security boundary enforced at the application layer (not OS-level sandboxing)
- New providers can be added by implementing a provider-specific loop function
- The fallback to plain completion ensures all providers remain functional

## Addendum: ReAct Parser Resilience (2026-03-01)

### Context

The text-based ReAct parser (`parser.py`) uses regex and JSON extraction to parse
`Thought:` / `Action:` / `Observation:` sequences from LLM output. A critical bug
was discovered where `json.loads()` rejected single-quoted Python dicts emitted by
LLMs (particularly Gemini). The root cause was `executor.py:_build_context()` using
`str(dict)` to format `tool_input` in history context.

### Decision

1. **Parser fallback**: Add `ast.literal_eval` as a fallback when `json.loads()` fails
   (see EXC-004 for security justification).
2. **Brace counting**: Updated to handle single-quoted strings during JSON extraction.
3. **Root cause fix** (proposed): Use `json.dumps()` in `_build_context()` to produce
   valid JSON in history, preventing LLMs from learning single-quote syntax.

### Agentic Continuation State

Follow-up messages after `/workflow` or `@role` invocations were incorrectly routed
through simple text streaming (no tools). Two state fields were added to `ConsoleApp`:

- `_agentic_mode: bool` — set `True` by `_handle_workflow()` and `_handle_role()`
- `_agentic_system_prompt: str | None` — stores the augmented system prompt

`_handle_chat()` checks `_agentic_mode` and routes accordingly. Reset on `/new`.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
