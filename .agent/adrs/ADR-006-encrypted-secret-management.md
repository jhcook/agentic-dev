# ADR-006: Encrypted Secret Management for Agent CLI

## Status
Accepted

## Context

The Agent CLI requires access to sensitive credentials for various operations:
- **LLM Provider API Keys**: OpenAI, Gemini, Anthropic, GitHub Copilot
- **Infrastructure Secrets**: Supabase service role keys
- **Future Integrations**: Additional third-party services

Previously, all secrets were stored as environment variables or in `.env` files, which presents several challenges:

1. **Security Risk**: Plaintext storage in shell configurations or `.env` files
2. **No Centralized Management**: Secrets scattered across different locations
3. **Compliance Gaps**: No audit trail for secret access (SOC2 requirement)
4. **Developer Experience**: Manual environment variable management
5. **Rotation Difficulty**: No mechanism for secure credential rotation

We need a secure, centralized secret management system that:
- Encrypts secrets at rest
- Provides audit logging for compliance
- Integrates seamlessly with existing configuration
- Maintains backward compatibility with environment variables

## Decision

We will implement a **file-based encrypted secret management system** integrated into the Agent CLI:

### Architecture

```
.agent/secrets/
├── .gitignore          # Prevents accidental commits
├── config.json         # Salt and metadata (no secrets)
├── supabase.json       # Encrypted Supabase secrets
├── openai.json         # Encrypted OpenAI secrets
├── gemini.json         # Encrypted Gemini secrets
└── anthropic.json      # Encrypted Anthropic secrets
```

### Encryption Scheme

- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Salt**: 16 bytes, randomly generated per installation
- **Nonce**: 12 bytes, randomly generated per encryption operation

### CLI Interface

```bash
agent secret init          # Initialize with master password
agent secret set <svc> <key> [--value]
agent secret get <svc> <key> [--show]
agent secret list [service]
agent secret delete <svc> <key>
agent secret import <service>   # From environment variables
agent secret export <service>   # To .env format
agent secret services           # List supported services
```

### Integration Pattern

```python
# In agent/core/config.py
def get_secret(key: str, service: Optional[str] = None) -> Optional[str]:
    # 1. Try secret manager (if initialized and unlocked)
    # 2. Fallback to os.getenv()
```

This provides **backward compatibility** - existing environment variables continue to work.

### Security Controls

- **File Permissions**: 700 for directory, 600 for files
- **Gitignore**: `.agent/secrets/` is gitignored by default
- **Audit Logging**: All secret operations logged (no values)
- **Password Strength**: Minimum 12 characters, mixed case + numbers

## Alternatives Considered

### Option A: System Keychain Integration
**Description**: Use macOS Keychain, Windows Credential Manager, or Linux Secret Service.

**Pros**:
- OS-level security
- No master password to remember
- Hardware security module support

**Cons**:
- Platform-dependent implementation
- Complex cross-platform testing
- May require elevated permissions
- Less portable across environments

**Decision**: Rejected for first iteration due to complexity. May revisit for future enhancement.

### Option B: External Secret Manager (HashiCorp Vault, AWS Secrets Manager)
**Description**: Integrate with enterprise secret management solutions.

**Pros**:
- Enterprise-grade security
- Centralized management for teams
- Access policies and rotation

**Cons**:
- Requires external infrastructure
- Additional cost
- Network dependency
- Overkill for individual developers

**Decision**: Rejected as primary solution. May add as optional integration.

### Option C: Environment Variables Only (Status Quo)
**Description**: Continue using environment variables and `.env` files.

**Pros**:
- Simple and familiar
- No additional tooling
- Works everywhere

**Cons**:
- Plaintext storage
- No audit trail
- No rotation mechanism
- No centralized management

**Decision**: Rejected as primary, but maintained as fallback for compatibility.

## Consequences

### Positive
1. **Security**: Secrets encrypted at rest with industry-standard algorithms
2. **Compliance**: Audit logging satisfies SOC2 requirements
3. **Developer Experience**: Unified CLI for secret management
4. **Portability**: Encrypted files can be backed up safely
5. **Backward Compatibility**: Environment variables still work
6. **Rotation Support**: Easy to update secrets via CLI

### Negative
1. **Master Password**: Users must remember/secure master password
2. **Unlock Required**: Some operations require unlocking first
3. **Additional Dependency**: Requires `cryptography` Python package
4. **Recovery**: Lost master password means re-creating all secrets

### Mitigations
- Password strength requirements reduce brute-force risk
- Export command allows backup to secure location
- Environment variable fallback provides recovery path

## Implementation

- **Story**: [INFRA-026](file:///Users/jcook/repo/agentic-dev/.agent/cache/stories/INFRA/INFRA-026-agent-secret-management-command.md)
- **Core Module**: `.agent/src/agent/core/secrets.py`
- **CLI Commands**: `.agent/src/agent/commands/secret.py`
- **Integration**: `.agent/src/agent/core/config.py` (`get_secret()` function)

## References

- [NIST SP 800-132: PBKDF Recommendations](https://csrc.nist.gov/publications/detail/sp/800-132/final)
- [AES-GCM Authentication](https://en.wikipedia.org/wiki/Galois/Counter_Mode)
- [Python cryptography library](https://cryptography.io/)
