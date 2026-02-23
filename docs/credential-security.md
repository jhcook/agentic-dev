# Credential Security in the Agentic Workflow: Safety Meets Absolute Convenience

In the shift toward heavily automated, AI-driven software development—the "Agentic Workflow"—your development environment is suddenly making hundreds of API calls an hour. It needs constant access to high-privilege credentials: API keys for Google Gemini, OpenAI, GitHub tokens, and database access keys for your various integrations.

The traditional approach of stuffing these into `.env` files scattered across multiple directories is no longer viable. It is a security nightmare waiting to happen (accidental commits, plaintext exposure to malware) and a massive headache for developer experience (copying and pasting tokens across laptops).

To build an enterprise-grade agentic system, security cannot come at the cost of developer velocity. That's why `agentic-dev` bakes credential management directly into the physical core of its systems, directly native-integrating with your operating system's secure enclave, such as the **macOS Keychain**, **Windows Credential Locker**, or **Linux Secret Service**.

## The Problem with `.env` Sprawl

When you rely on plain-text environment files:
1. **They leak.** A single `.gitignore` mistake exposes your master database credentials to the world.
2. **They are unencrypted.** Anyone (or any malicious script) with read access to your filesystem can immediately steal your production keys.
3. **They lack auditability.** There is no record of when a key was accessed or rotated.

## The Solution: A Native, Encrypted Agent Vault

`agentic-dev` features a built-in `SecretManager` that stores all credentials locally on disk using industry-standard **AES-256-GCM** authenticated encryption.

When you run `agent secret init`, the system generates a massive cryptographic salt and derives an encryption key from your master password using **PBKDF2-HMAC-SHA256 with 100,000 iterations** per security standards. The individual service keys are then heavily encrypted at rest in the `.agent/secrets/` directory.

But here is where the magic happens: **You don't have to keep typing a master password.**

### The Convenience of Native OS Keyring Integration

Security protocols only succeed if developers actually embrace using them. If engineers are forced to type a complex master password every time they run `agent implement` or `agent pr`, human nature dictates they will eventually bypass the security, use trivial passwords, or abandon the workflow entirely.

By directly integrating the `SecretManager` with the native **System Keyring**, the system achieves deep, zero-friction security across all major operating systems:
- **macOS**: Apple Keychain
- **Windows**: Windows Credential Locker
- **Linux**: Secret Service API (e.g., GNOME Keyring, KDE KWallet)

When you authenticate via `agent secret login`:
1. The CLI verifies your master password.
2. It offloads that master key to be securely stored *inside your OS's native keyring*.
3. Every subsequent time an `agent *` command runs, the CLI silently and securely retrieves the key from the OS keyring through secure IPC, unlocking the vault in memory in milliseconds.

The developer experiences the pure operational convenience of plain-text `.env` variables—the agent "just works"—but under the surface, the credentials remain encrypted at rest and guarded by the operating system's hardware-backed secure storage mechanisms.

### Built for the Remote Enterprise

This native architecture scales perfectly into governed, enterprise environments with distributed workforces:

- **SOC2 Compliance via Structured Logging:** Every time a secret is accessed, rotated, or imported, the system drops a structured, non-sensitive JSON audit log (`SECRET_OP`). Security teams know *who* accessed *what* service, and *when*, without ever logging or exposing the actual secret value.
- **Graceful Password Rotation:** By running `agent secret rotate-key`, the system safely backs up your encrypted secrets, unlocks and re-encrypts the entire volume under a newly derived key, and safely replaces the secrets atomically.
- **Headless CI/CD Support:** For remote environments like GitHub Actions, the system gracefully bypasses the unavailable OS Keychain by detecting an `AGENT_MASTER_KEY` variable from the CI runner, maintaining its strict decrypted-only-in-memory pipeline without compromising the local developer experience.

## Zero Trade-offs

The core philosophy of `agentic-dev` is that doing the right thing for security should be the absolute easiest path for an engineer.

By pushing high-entropy, AES-256 encrypted credentials to the local disk and delegating the decryption unlock sequence to the native OS keyring, developers keep the frictionless magic of rapid AI prototyping, fully backed by unforgiving, enterprise-grade cryptographic guarantees.
