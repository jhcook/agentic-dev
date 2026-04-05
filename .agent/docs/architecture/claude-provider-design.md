# Architecture Review: Claude Provider with Bedrock Support

## Overview

INFRA-185 introduces a `claude` provider capable of auto-detecting AWS Bedrock configurations from the standard `~/.claude/settings.json` file used by Claude Code. This allows the agent to inherit existing SSO sessions and regional configurations without redundant setup.

## Component Design

**1. Configuration Loader**
- **Path**: `~/.claude/settings.json` (resolved via `Path.home()`)
- **Precedence**: Environment variables take absolute priority. If `AWS_REGION` is set in the shell, it will not be overwritten by the value in `settings.json`.
- **Shadowing Prevention**: Variables are injected using `os.environ.setdefault(key, value)`.

**2. SSO Credential Refresh**
- **Command**: `awsAuthRefresh` field from JSON.
- **Execution Safety**: Uses `subprocess.run` with `shell=False` after `shlex.split`. 
- **Timeout**: 60 seconds. Failures are logged at `WARNING` level but do not block client instantiation (allowing existing valid sessions to proceed).

**3. Client Factory**
- **Logic**: 
  - If `CLAUDE_CODE_USE_BEDROCK == "1"` -> `AnthropicBedrock` client.
  - Else -> `Anthropic` client (standard API key).
- **Validation**: If neither an API key nor Bedrock configuration is present, a typed `AIConfigurationError` is raised with instructions for `agent onboard`.

## Security & Compliance

- **Credential Leakage**: No credentials from the settings file or environment are logged. Only the selection of the client type (Bedrock vs. Direct) is recorded in structured logs.
- **Permissions**: The agent operates under the user's local AWS identity (typically via `AWS_PROFILE`). No static secrets are stored within the codebase.

## Alignment with ADRs

- **ADR-046**: Implements structured logging for client construction and shell command execution results.

## Copyright

Copyright 2026 Justin Cook
