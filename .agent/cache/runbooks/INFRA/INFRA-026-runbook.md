# INFRA-026: Agent Secret Management Command

## State
ACCEPTED

## Goal Description
To design, implement, and document a secure and flexible secret management system integrated into the Agent CLI. This will enable developers to securely manage API keys and credentials using a centralized, encrypted storage system that supports key rotation, encrypted storage, seamless integration, and audit logging.

## Panel Review Findings

### **@Architect**:
- The overall architecture seems solid and aligns with the functional and non-functional requirements.
- The integration of AES-256-GCM ensures robust encryption. Using `PBKDF2` for key derivation aligns with industry standards, but particular care must be taken to select a suitable number of iterations to avoid performance issues during decryption.
- Integration across different components shows a good separation of concerns. However, the fallback to environment variables introduces a potential lack of control over these sensitive values; an automatic prompt to migrate environment variables to the secret manager could enhance security.
- It is critical to ensure scalability in handling large numbers of secrets since developers may deal with numerous microservices, each requiring multiple secrets.

### **@Security**:
- The usage of AES-256-GCM with PBKDF2 for key derivation is a secure approach. However, the master password must be adequately protected during interactive processes and not echo in the terminal.
- It is essential to implement rate-limiting and temporary lockout mechanisms for repeated incorrect master password attempts to mitigate brute-force attacks.
- Consider implementing a secure random generator for salt values and periodically updating the master password.
- The audit logging mechanism should follow the principle of least privilege and avoid logging key details (e.g., keys should never appear in their plaintext or encrypted forms in the logs).
- Verify masking logic in the `list` command to prevent accidental leakage of secrets.

### **@QA**:
- The test strategy is well thought out and covers unit, integration, and security testing. However, consider expanding edge-case testing, such as corrupted encrypted files, missing permissions on the `.agent/secrets/` directory, and API key retrieval for undefined services.
- Document clear test cases for the CLI commands, focusing on inputs/outputs and error handling (e.g., invalid commands, missing flags).
- Ensure backward compatibility tests are in place for the fallback mechanism to environment variables.
- Confirm test data for integration testing does not include real secrets and adheres to GDPR compliance.

### **@Docs**:
- The CLI commands and their usage should be fully documented in `.agent/docs/`. Examples for each subcommand (`init`, `set`, `get`, etc.) will improve usability.
- A detailed migration guide should explain how to import pre-existing environment variables into the secret manager (e.g., instructions for `agent secret import`).
- Update the Developer Onboarding guide to reflect these changes and remove outdated instructions for `.env` setup.
- Define the structure and fields stored in `.agent/secrets/` in documentation to help engineers and users understand the design.
- Include a glossary of terms, such as "PBKDF2", "AES-256-GCM", "master password", etc., for less experienced developers.

### **@Compliance**:
- The logging mechanism must ensure compliance with SOC2 and GDPR. Ensure no sensitive data (e.g., PII or plaintext credentials) is logged either intentionally or due to poorly masked display logic.
- The rollback plan of encrypted secrets to `.env` format should clarify how it ensures data compliance during the recovery phase.
- Documentation must include SOC2 compliance notes, showcasing how the system meets requirements for securing and rotating secrets while maintaining access visibility.
- All relevant ADRs should be referenced, following governance rules (`adr-standards.mdc`). A new ADR must document the architectural choice of secret management.
- Add a validation step in the CI pipeline to confirm no secrets are stored in plaintext or committed to the repository, as per governance guidance.

### **@Observability**:
- Ensure audit logs include critical metadata, such as timestamps, operation type (e.g., `set`, `get`, etc.), user/agent ID, and status. This should integrate with existing observability pipelines.
- Logs should be aggregated in the same logging platform as other Agent CLI events, with a tag to allow easy filtering of secret management events for investigation purposes.
- Metrics for usage patterns (e.g., frequency of secret access to LLM providers) are vital for detecting anomalies or security breaches.
- Provide alerts on failed decryption or authentication attempts with configurable thresholds.

## Implementation Steps

### Phase 1: Core Secret Management Module

#### NEW `.agent/src/agent/core/secrets.py`

Create the core `SecretManager` class with the following structure:

```python
class SecretManager:
    """Manages encrypted secret storage using AES-256-GCM."""
    
    def __init__(self, secrets_dir: Path):
        self.secrets_dir = secrets_dir
        self.config_file = secrets_dir / "config.json"
        self._master_key = None  # Cached in memory
        
    def initialize(self, master_password: str) -> None:
        """Initialize secret storage with master password."""
        # Generate salt, derive key using PBKDF2 (100,000 iterations)
        # Create config.json with salt and metadata
        # Set directory permissions to 700, files to 600
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2-HMAC-SHA256."""
        # Use 100,000 iterations minimum
        # Return 32-byte key for AES-256
        
    def encrypt_value(self, plaintext: str) -> Dict[str, str]:
        """Encrypt value using AES-256-GCM."""
        # Return {"ciphertext": base64, "nonce": base64, "tag": base64}
        
    def decrypt_value(self, encrypted: Dict[str, str]) -> str:
        """Decrypt value using AES-256-GCM."""
        # Verify tag, decrypt ciphertext
        
    def set_secret(self, service: str, key: str, value: str) -> None:
        """Store encrypted secret."""
        # Load service file (e.g., supabase.json)
        # Encrypt value
        # Save atomically
        # Log audit event
        
    def get_secret(self, service: str, key: str) -> Optional[str]:
        """Retrieve and decrypt secret."""
        # Try secret manager first
        # Fall back to os.getenv() if not found
        # Log audit event (no secret value in log)
        
    def list_secrets(self, service: Optional[str] = None) -> Dict:
        """List all secrets (masked)."""
        # Return structure: {service: {key: "***masked***"}}
        
    def delete_secret(self, service: str, key: str) -> None:
        """Delete a secret."""
        # Remove from service file
        # Log audit event
```

**Key Implementation Details:**
- **Encryption**: Use `cryptography` library's `Fernet` or `AESGCM`
- **PBKDF2**: 100,000+ iterations with SHA-256
- **File Permissions**: Use `os.chmod(path, 0o600)` for files, `0o700` for directory
- **Atomic Writes**: Write to `.tmp` file, then `os.replace()`
- **Compliance**: Call `scrub_sensitive_data()` before any logging

---

### Phase 2: CLI Command Interface

#### NEW `.agent/src/agent/commands/secret.py`

Implement Typer command group:

```python
import typer
from rich.console import Console
from agent.core.secrets import SecretManager
from agent.core.config import config

app = typer.Typer(
    name="secret",
    help="Manage encrypted secrets for API keys and credentials.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()

@app.command(name="init")
def init():
    """Initialize secret management with master password."""
    # Prompt for master password (use getpass, no echo)
    # Confirm password
    # Validate strength (min 12 chars, complexity)
    # Create .agent/secrets/ directory
    # Initialize SecretManager
    # Create .gitignore
    
@app.command(name="set")
def set_secret(
    service: str,
    key: str,
    value: str = typer.Option(None, "--value", prompt=True, hide_input=True)
):
    """Set a secret value."""
    # Prompt for master password
    # Validate service/key format
    # Store encrypted secret
    # Confirm success
    
@app.command(name="get")
def get_secret(
    service: str,
    key: str,
    show: bool = typer.Option(False, "--show", help="Display unmasked value")
):
    """Get a secret value."""
    # Prompt for master password
    # Retrieve secret
    # Display masked or unmasked based on --show flag
    
@app.command(name="import")
def import_secrets(service: str):
    """Import secrets from environment variables."""
    # Define service mappings:
    #   supabase: SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY
    #   openai: OPENAI_API_KEY
    #   gemini: GEMINI_API_KEY, GOOGLE_GEMINI_API_KEY
    #   anthropic: ANTHROPIC_API_KEY
    # Read from environment
    # Store each as encrypted secret
    # Report imported count
```

**Error Handling:**
- Invalid master password: "Incorrect password. X attempts remaining."
- Missing service file: "Service '{service}' not configured."
- Permission errors: "Cannot write to .agent/secrets/. Check permissions."

---

### Phase 3: Integration with Existing Code

#### MODIFY `.agent/src/agent/core/config.py`

Add helper function:

```python
def get_secret(key: str, service: Optional[str] = None) -> Optional[str]:
    """Get secret from secret manager or environment variable."""
    # Try secret manager first (if initialized)
    try:
        from agent.core.secrets import secret_manager
        if service and secret_manager.is_initialized():
            value = secret_manager.get_secret(service, key)
            if value:
                return value
    except Exception:
        pass  # Fall back to environment
    
    # Fallback to environment variable
    return os.getenv(key)
```

Update `get_provider_config()`:

```python
def get_provider_config(provider_name: str) -> Optional[Dict[str, Optional[str]]]:
    """Retrieve provider configuration from secrets or environment."""
    config_map = {
        "openai": {"api_key": get_secret("api_key", "openai") or os.getenv("OPENAI_API_KEY")},
        "gemini": {"api_key": get_secret("api_key", "gemini") or os.getenv("GEMINI_API_KEY")},
        "anthropic": {"api_key": get_secret("api_key", "anthropic") or os.getenv("ANTHROPIC_API_KEY")},
    }
    return config_map.get(provider_name.lower())
```

#### MODIFY `.agent/src/agent/core/ai/service.py`

Replace direct `os.getenv()` calls:

**Lines 54, 66, 80, 267:**
```python
# Before
gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

# After
from agent.core.config import get_secret
gemini_key = get_secret("api_key", "gemini") or \
             os.getenv("GOOGLE_GEMINI_API_KEY") or \
             os.getenv("GEMINI_API_KEY")
```

#### MODIFY `.agent/src/agent/main.py`

Register secret command:

```python
from agent.commands import secret

app.add_typer(secret.app, name="secret")
```

---

### Phase 4: Security & Compliance

#### NEW `.agent/secrets/.gitignore`

```
# Never commit secrets
*.json
!.gitignore

# Backup files
*.bak
*.backup
*.tmp
```

#### MODIFY `.agent/src/agent/core/governance.py`

Add preflight check:

```python
def check_secret_security() -> List[str]:
    """Validate secret management security."""
    issues = []
    
    secrets_dir = Path(".agent/secrets")
    if secrets_dir.exists():
        # Check directory permissions (should be 700)
        stat = secrets_dir.stat()
        if stat.st_mode & 0o777 != 0o700:
            issues.append("Secret directory has insecure permissions")
        
        # Check .gitignore exists
        if not (secrets_dir / ".gitignore").exists():
            issues.append("Missing .gitignore in secrets directory")
        
        # Check for plaintext secrets in JSON files
        for json_file in secrets_dir.glob("*.json"):
            if json_file.name == "config.json":
                continue
            # Verify all values are encrypted (contain 'ciphertext' field)
            
    return issues
```

#### NEW `.agent/src/agent/core/audit.py`

Implement audit logging:

```python
import logging
import json
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

def log_secret_operation(
    operation: str,
    service: str,
    key: str,
    status: str,
    user: str = "agent"
) -> None:
    """Log secret management operation for SOC2 compliance."""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "operation": operation,  # init, set, get, delete, import, export
        "service": service,
        "key": key,  # Key name only, never the value
        "status": status,  # success, failed, unauthorized
        "user": user,
        "component": "secret_manager"
    }
    
    # Log as structured JSON (no sensitive data)
    logger.info(f"SECRET_OP: {json.dumps(audit_entry)}")
```

---

### Phase 5: Testing Infrastructure

#### NEW `tests/test_secrets.py`

```python
import pytest
from agent.core.secrets import SecretManager

def test_encryption_decryption():
    """Test AES-256-GCM encryption round-trip."""
    
def test_pbkdf2_key_derivation():
    """Test PBKDF2 with 100k iterations."""
    
def test_secret_storage_retrieval():
    """Test storing and retrieving secrets."""
    
def test_fallback_to_environment():
    """Test fallback when secret not found."""
    
def test_file_permissions():
    """Test 600 permissions on secret files."""
```

#### NEW `tests/test_secret_command.py`

```python
from typer.testing import CliRunner
from agent.commands.secret import app

def test_init_command():
    """Test agent secret init."""
    
def test_set_get_commands():
    """Test agent secret set/get."""
    
def test_import_command():
    """Test agent secret import supabase."""
```
  
## Verification Plan

### Automated Tests
- [x] Test secrets manager ensures AES-256-GCM encryption and PBKDF2 key derivation work consistently.
- [x] Verify secret import/export from and to environment variables and `.env` files.
- [x] Validate backward compatibility for configurations using existing environment variables.

### Manual Verification
- [ ] Verify the CLI commands flow comprehensively: init, set, get, list, delete, import, export.
- [ ] Perform compliance validation by running a simulated SOC2 audit for secret management operations.
- [ ] Test with invalid master passwords for expected errors and messages.

## Definition of Done

### Documentation
- [ ] Instructions for CLI commands added to `README.md`.
- [ ] Migration guide added to `docs/`.
- [ ] Glossary added for encryption-specific terms.
- [ ] Ensure ADR for Secret Management Architecture is created and referenced in implementation.

### Observability and Security
- [ ] Audit logs for all secret management operations integrate with existing logging solutions.
- [ ] Default logs include operation type, user ID, and timestamps (no sensitive data).
- [ ] Metrics provided for secret usage and errors.
- [ ] Failed decryption attempts trigger alert notifications.

### Deployment Readiness
- [ ] Compliance preflight check incorporated in `agent preflight`.
- [ ] CI pipeline validates the absence of plaintext secrets or configuration.
- [ ] Backward compatibility verified.

### Testing
- [ ] 100% test coverage for `SecretsManager`.
- [ ] Unit and integration tests pass successfully.
- [ ] Manual testing checklist completed.