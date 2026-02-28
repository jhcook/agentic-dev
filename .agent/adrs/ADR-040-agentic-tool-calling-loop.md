# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ADR-040: Agentic Tool-Calling Loop Architecture

## Status

Accepted

## Date

2026-02-27

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

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
