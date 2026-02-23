# NotebookLM Authentication Guide

This guide walks you through the process of authenticating the agent with Google NotebookLM using the Model Context Protocol (MCP). Because NotebookLM currently lacks a dedicated API or service account mechanism, authentication is performed via browser session cookies.

## Walkthrough

The `agent mcp auth notebooklm` command provides multiple ways to provide your session cookies.

### 1. Automatic Extraction (Recommended)
You can automatically extract active session cookies from your local browser (Chrome, Edge, Firefox, etc.) without needing to open Developer Tools.

Run the following command:

```bash
agent mcp auth notebooklm --auto
```

This command will:
1. Display a GDPR informed consent prompt explaining that sensitive session cookies will be read. You must type `y` to proceed.
2. Ask for your OS Keychain / Keyring password (if prompted by your OS) to securely store the extracted cookies.
3. Successfully save the cookies to the encrypted SecretManager.

### 2. Manual File Import
If you prefer not to use automatic extraction, you can manually extract the cookies and provide them in a JSON file.

1. Open your browser and navigate to <https://notebooklm.google.com>
2. Open Developer Tools (F12) -> **Application** (or Storage) -> **Cookies**
3. Copy the values for `SID`, `HSID`, and `SSID`.
4. Create a JSON file (e.g., `cookies.json`) with these values.
5. Run the command:

```bash
agent mcp auth notebooklm --file path/to/cookies.json
```

### 3. Clear Session
If you need to switch accounts or clear your cached credentials, use the `--clear-session` flag:

```bash
agent mcp auth notebooklm --clear-session
```

## Security Considerations

- **Highly Sensitive Credentials:** The `SID`, `HSID`, and `SSID` cookies act as equivalent credentials to your Google Account login. They can grant broad access to your account.
- **Secure Storage:** The agent never stores these cookies in plain text on disk. They are encrypted and stored in the OS-native keychain using the local `SecretManager`.
- **In-Memory Processing:** During automatic extraction, the cookies are briefly processed in memory and immediately passed to the secure storage layer.
- **Explicit Consent:** Automatic extraction requires explicit user consent, defaulting to denial (No), establishing a lawful basis for data processing under GDPR.

## Troubleshooting

### "browser-cookie3 not installed" or Extraction Failure
If the `--auto` extraction fails, you may see an error about `browser-cookie3` or that the cookies could not be found.
**Solution:** Ensure you are actively logged into <https://notebooklm.google.com> on a supported local browser. If extraction continues to fail, fallback to the manual `--file` method.

### "Secret manager already initialized" or unlocking issues
If you receive secret manager errors:
- If your SecretManager is locked, the agent will prompt you for your master password (or attempt to use `AGENT_MASTER_KEY`).
- If you forgot your master password, you may need to reset your secret bindings or rotate your keys.

### Session Expired
If your NotebookLM queries start failing with unauthorized errors, your session cookies may have expired.
**Solution:** Re-run the authentication command (`agent mcp auth notebooklm --auto`) to refresh the stored cookies from your active browser session.
