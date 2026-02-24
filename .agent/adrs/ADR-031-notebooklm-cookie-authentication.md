# ADR-031: NotebookLM Cookie Authentication

## Status

ACCEPTED

## Context

NotebookLM does not provide a traditional API key or service account authentication method. The only way to interact with its undocumented API via the MCP server is by using the user's active session cookies (`SID`, `HSID`, `SSID`). We need a reliable and user-friendly way to extract these cookies and provide them to the MCP server securely.

## Decision

We will implement a cookie-based authentication flow. Users can either provide a JSON file containing the cookies (`--file`), receive instructions for manual extraction (`--no-auto-launch`), or use an automated extraction method (`--auto`) that reads cookies directly from the local browser's SQLite database. The automated extraction will use the `browser_cookie3` library. Since these cookies provide full access to the user's Google account, we will strictly filter for only the necessary cookies (`SID`, `HSID`, `SSID`) and store them securely using the OS-native keychain via our `SecretManager`. **Crucially, user consent is defined as the lawful basis for this cookie processing (GDPR Article 6(1)(a)), and this consent must be explicitly obtained before the `--auto` extraction can proceed.**

## Alternatives Considered

- **Service Accounts / API Keys**: Rejected because Google does not currently offer an official API or service account support for NotebookLM.
- **Short-Lived API Tokens**: Rejected because the NotebookLM MCP server requires raw cookies; there is no endpoint to exchange cookies for a scoped token.
- **Manual Input Only**: Considered too tedious and error-prone for users to manually open DevTools and copy cookie strings.

## Consequences

- **Positive**: Provides a seamless authentication experience for the user. Enables automated sync and tool execution.
- **Negative**: Relies on a third-party library (`browser_cookie3`) which may break if browser cookie storage formats change. Extracting `SID`, `HSID`, and `SSID` carries significant security risks, requiring strict explicit user consent (GDPR Article 6(1)(a)) and secure storage.

## Supersedes

None

## Copyright

Copyright 2026 Justin Cook
