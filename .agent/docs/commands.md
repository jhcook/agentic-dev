# AI-Powered CLI Commands

This document provides details about the AI-related commands in the CLI (`implement`, `match-story`, `new-runbook`, `pr`).

## `--provider` Option

### Purpose
The `--provider` option allows developers to select an AI provider (`gh`, `gemini`, `openai`) explicitly. This enables flexibility while ensuring the proper provider is configured before use.

### Accepted Values
- `gh` (default)
- `gemini`
- `openai`

### Default Behavior
If the `--provider` flag is omitted, the system defaults to the `gh` provider, assuming it is correctly configured. If `gh` is not configured, the system will raise a `RuntimeError`.

### Configuration Prerequisites
To use an AI provider, the appropriate environment variables or configuration keys must be set:

- **`gh`**: Requires appropriate GitHub access configuration (if any).
- **`gemini`**: Requires `GEMINI_API_KEY` environment variable or configuration setting.
- **`openai`**: Requires `OPENAI_API_KEY` to be set in the environment or configuration.

For example: