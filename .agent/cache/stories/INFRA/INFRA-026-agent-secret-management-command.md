# INFRA-026: Agent Secret Management Command

## State
COMMITTED

## Problem Statement
The Agent CLI currently relies on environment variables (e.g., `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) scattered across the codebase using `os.getenv()`. This approach has several issues:
- **Security Risk**: Secrets are stored in plaintext in `.env` files or shell configurations
- **No Centralized Management**: No unified way to view, update, or rotate secrets
- **Poor Developer Experience**: Developers must manually manage multiple environment variables
- **Compliance Concerns**: No audit trail for secret access (SOC2 requirement)
- **No Encryption**: Secrets are stored in plaintext on disk

We need a secure, centralized secret management system integrated into the Agent CLI.

## User Story
As a **developer using the Agent CLI**, I want **a secure command to manage secrets** so that **I can store API keys and credentials encrypted at rest with proper audit logging and easy rotation**.

## Acceptance Criteria
- [x] **AC1: Secret Storage**: Secrets are encrypted using AES-256-GCM and stored in `.agent/secrets/` directory
- [x] **AC2: CLI Commands**: Implement `agent secret` with subcommands: `init`, `set`, `get`, `list`, `delete`, `import`, `export`
- [x] **AC3: Supabase Integration**: Support storing Supabase API keys (`service_role_key`, `anon_key`)
- [x] **AC4: LLM Provider Integration**: Support storing API keys for OpenAI, Gemini, Anthropic, GitHub
- [x] **AC5: Fallback Mechanism**: Gracefully fall back to environment variables if secrets not configured
- [x] **AC6: Import from Environment**: `agent secret import <service>` imports existing env vars
- [x] **AC7: Security**: `.agent/secrets/` is gitignored and files have 600 permissions
- [x] **AC8: Master Password**: Secrets encrypted with master password using PBKDF2 key derivation
- [x] **AC9: Integration**: Update `config.py` and `service.py` to use secret manager
- [x] **AC10: Masked Display**: `agent secret list` shows masked values by default, `--show` flag reveals

## Non-Functional Requirements

### Security
- **Encryption at Rest**: AES-256-GCM encryption for all secret values
- **Key Derivation**: PBKDF2 with salt for master password
- **File Permissions**: Restrict secret files to 600 (owner read/write only)
- **No Plaintext Storage**: Never store secrets in plaintext
- **Gitignore**: Ensure `.agent/secrets/` is never committed to version control

### Compliance
- **SOC2**: Audit logging for all secret access operations
- **GDPR**: No PII in logs, secure data handling
- **Governance**: Preflight checks validate no plaintext secrets in code

### Performance
- **Fast Retrieval**: Secret decryption should be < 10ms
- **Caching**: Cache decrypted secrets in memory for session duration
- **Lazy Loading**: Only decrypt secrets when accessed

### Observability
- **Audit Trail**: Log all secret operations (set, get, delete) with timestamps
- **Metrics**: Track secret access patterns for security monitoring
- **Error Handling**: Clear error messages for common issues (wrong password, missing secrets)

## Linked ADRs
- ADR-006: Encrypted Secret Management for Agent CLI

## Impact Analysis Summary

### Components Touched
- **New**: `.agent/src/agent/core/secrets.py` - Secret management module
- **New**: `.agent/src/agent/commands/secret.py` - CLI command interface
- **Modified**: `.agent/src/agent/core/config.py` - Integration with secret manager
- **Modified**: `.agent/src/agent/core/ai/service.py` - Use secrets for API keys
- **Modified**: `.agent/src/agent/main.py` - Register secret command
- **New**: `.agent/secrets/` - Secret storage directory

### Workflows Affected
- **Developer Onboarding**: New developers use `agent secret import` instead of manual `.env` setup
- **CI/CD**: Use `agent secret export` for environment variable generation
- **Secret Rotation**: Use `agent secret set` to update credentials

### Risks Identified
- **Migration Risk**: Existing `.env` files need migration path
- **Password Management**: Users must remember master password
- **Backward Compatibility**: Must maintain fallback to environment variables

## Test Strategy

### Unit Tests
- `tests/test_secrets.py`:
  - Test encryption/decryption with various inputs
  - Test secret storage and retrieval
  - Test master password validation
  - Test key derivation (PBKDF2)
  - Test fallback to environment variables

### Integration Tests
- `tests/test_secret_command.py`:
  - Test all CLI subcommands (init, set, get, list, delete, import, export)
  - Test secret manager integration with config module
  - Test AI provider initialization with secrets
  - Test error handling (wrong password, missing secrets)

### Security Tests
- Verify encrypted storage format (no plaintext)
- Test file permissions (600)
- Validate gitignore configuration
- Test master password strength requirements
- Verify audit logging

### Manual Verification
1. Initialize: `agent secret init`
2. Import: `agent secret import supabase` (imports SUPABASE_SERVICE_ROLE_KEY)
3. List: `agent secret list`
4. Get: `agent secret get supabase service_role_key --show`
5. Integration: `agent query "test"` (verify uses secret manager)
6. Preflight: `agent preflight` (verify compliance)

## Rollback Plan
1. **Immediate Rollback**: Revert code changes, secrets remain encrypted (no data loss)
2. **Fallback Mechanism**: Environment variables continue to work during transition
3. **Export Secrets**: Use `agent secret export <service>` to recover to `.env` format
4. **Database Backup**: `.agent/backups/` contains timestamped config backups
