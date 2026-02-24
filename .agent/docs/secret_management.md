# Secret Management

The Agentic Development Tool (`agent`) provides a secure, encrypted keyring for managing sensitive credentials such as API keys and authentication tokens. This ensures that sensitive data is NEVER stored in plain-text configuration files or committed to version control.

## `agent secret` vs `agent config`

It is very important to understand the difference between the `secret` and `config` namespaces:

* **`agent config`**: Stores general, non-sensitive settings (like timeouts, provider names, or max concurrent allowed API calls). These values are written **in plain text** to `.agent/etc/agent.yaml`.
* **`agent secret`**: Stores highly sensitive values (like API keys, Notion tokens, or GitHub tokens). These values are encrypted using AES-256 and stored in the OS-native keyring or a local `.env.secrets` file (which should be gitignored).

**CRITICAL RULE:** Never use `agent config set env.<VARIABLE>` to store API keys.

## Using the Secret Manager

The `agent secret` command group provides the interface for interacting with the secure keyring.

### Storing a Secret

To store a new secret, use `agent secret set <namespace> <key>`. For example, setting an API key for the OpenAI provider:

```bash
agent secret set openai api_key
# You will be interactively prompted to securely enter the value
```

Other examples:

```bash
agent secret set notion notion_token
agent secret set gemini api_key
```

### Retrieving a Secret

To check if a secret is stored (or retrieve its value), use:

```bash
agent secret get <namespace> <key>
# Example
agent secret get openai api_key
```

### Deleting a Secret

To remove a secret from the keyring:

```bash
agent secret delete <namespace> <key>
# Example
agent secret delete openai api_key
```

### Listing all Secret Namespaces

To see which namespaces currently have configured secrets (values are not shown):

```bash
agent secret list
```

## How it works

The agent uses a master key (`AGENT_MASTER_KEY`) to AES-256 encrypt your secrets. By default:
1. It attempts to use your Operating System's native keyring (e.g., macOS Keychain, Windows Credential Locker) via the `keyring` Python library.
2. If the OS keyring is unavailable or headless (like in CI environments), it falls back to storing the encrypted payload locally.

The `SecretManager` abstraction within the agent source code handles these fallbacks gracefully without requiring manual intervention from developers.

## Copyright

Copyright 2026 Justin Cook
