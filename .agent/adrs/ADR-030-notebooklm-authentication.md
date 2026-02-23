<!--
 Copyright 2026 Justin Cook

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->
# ADR-030: NotebookLM Authentication Pattern

## Status
Accepted

## Context
Agentic-dev requires integration with Google NotebookLM via the Model Context Protocol (MCP) to access the Oracle Preflight Pattern context. However, NotebookLM's browser-cookie3 extraction mechanism currently necessitates intercepting active session cookies (SID, HSID, SSID) from the user's browser, which poses a security and privacy risk if not handled correctly. We need a secure and user-consented method to extract and store these session tokens.

## Decision
1. **Explicit GDPR Consent:** Before invoking automatic cookie extraction across browsers, the `agent mcp auth notebooklm --auto` command will prompt the user with a distinct warning outlining that highly sensitive active Google session cookies are being read.
2. **Secure Persistence via SecretManager:** Plain text cookies will never be written to disk. The extracted tokens are immediately persisted to the OS-native Keychain (via macOS Keychain / SecretManager) in an encrypted format.
3. **Manual Fallback Mechanism:** Users who reject automatic extraction or prefer a safer alternative can manually provide cookies using the `--file` flag or retrieve documentation instructions via the `--no-auto-launch` flag.

## Consequences
**Positive:**
- Increased security by keeping session cookies off plain-text disk storage.
- Meets compliance (GDPR) standards via explicit informed consent prior to sensitive data processing.
- Avoids blocking CI/CD pipelines and manual environments where auto-extraction fails, falling back to manual or file-based workflows.

**Negative:**
- Forces the user to manage a secure keychain connection (and potentially password prompts to unlock).
- More complex authentication orchestration compared to a simple file dump.
