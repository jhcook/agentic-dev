# Console Personality Configuration

The interactive `agent console` supports configurable personality and repository context
through the `console` section in `.agent/etc/agent.yaml`.

## Configuration Keys

| Key | Type | Description |
|-----|------|-------------|
| `console.personality_file` | `string` | Path to a repo context file, resolved **relative to the repo root**. Example: `GEMINI.md`, `.github/copilot-instructions.md` |
| `console.system_prompt` | `string` | Inline personality preamble injected at the top of the system prompt |

## How It Works

The system prompt is composed from three layers:

1. **Personality Layer** — `console.system_prompt` defines the agent's tone and behavior
2. **Repo Context Layer** — `console.personality_file` injects repository-specific instructions (roles, conventions, philosophy)
3. **Runtime Context Layer** — Automatically generated (repo name, license header, project layout)

When **neither** key is set, the console uses the original hardcoded prompt unchanged — no configuration needed for the default experience.

## Example Configuration

```yaml
# .agent/etc/agent.yaml
console:
  # Path relative to repo root — supports any location the admin chooses
  personality_file: GEMINI.md
  # Direct personality preamble
  system_prompt: |
    You are a collaborative pair-programmer embedded in this repository.
    You work alongside the developer — proactive but never surprising.

    ## Communication Style
    - Be a good mentor and coach
    - Do not execute destructive actions without explicit user approval
    - Explain your reasoning when making decisions
    - Ask for clarification rather than assuming
```

## Security

- The `personality_file` path is resolved relative to the repo root
- **Path traversal is blocked** — paths that resolve outside the repo root (e.g., `../../etc/passwd`) are rejected with a warning log
- Missing files are handled gracefully — the prompt continues without the file content

## Relationship to GEMINI.md

`GEMINI.md` serves as repository context (roles, philosophy, workflows) while `system_prompt` controls the agent's personality and communication style. This separation allows the same repo context to work with different AI providers and personality configurations.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
