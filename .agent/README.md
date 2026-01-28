# Agentic Development Tool

This tool is designed to streamline and enhance the development process through automation and governance. It provides a suite of commands for linting, checking, fixing, and explaining code, as well as managing stories and conducting governance audits.

## Commands

### `agent lint`

Lints the codebase to identify and report style issues and potential errors. This command helps maintain code quality and consistency.

### `agent check`

Performs static analysis to detect potential bugs, security vulnerabilities, and code smells. This command ensures code reliability and security.

### `agent fix`

Automatically fixes certain types of linting errors and code smells. This command speeds up the development process by automating routine corrections.

### `agent explain`

Explains complex code snippets in plain language, making it easier for developers to understand unfamiliar code.

### `agent preflight`

Validates the agent's configuration before the agent is deployed to address governance concerns.

### `agent story`

Aids in managing and tracking user stories throughout the development lifecycle.

### `agent audit`

Executes a governance audit of the repository to assess traceability, identify stagnant code, and flag orphaned governance artifacts. This command helps ensure compliance and maintain code quality.

See [Command Documentation](docs/commands.md) for full usage options (e.g., `--fail-on-error`, `.auditignore`).

Usage: