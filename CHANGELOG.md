## [Unreleased]
### Added
- Introduced a `--provider` option for AI-powered CLI commands (`implement`, `match-story`, `new-runbook`, `pr`) to allow specifying an AI provider.
  - Supported providers: `gh`, `gemini`, `openai`
  - The system validates the provider against available configurations and raises appropriate errors:
    - `ValueError` for unsupported provider names.
    - `RuntimeError` for missing configuration of a valid provider.
  - Default provider (`gh`) is used if `--provider` is omitted and is properly configured.

Refer to `docs/commands.md` for details.