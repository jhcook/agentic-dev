# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Secret Management Module for Agent CLI.

Provides encrypted storage for API keys and credentials using AES-256-GCM
with PBKDF2 key derivation. Supports SOC2 compliance with audit logging.
"""

import base64
import json
import logging
import os
import stat
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# PBKDF2 configuration - 100,000 iterations per security standards
PBKDF2_ITERATIONS = 100_000
SALT_LENGTH = 16
KEY_LENGTH = 32  # AES-256
NONCE_LENGTH = 12  # GCM standard nonce size

# Service to environment variable mappings
SERVICE_ENV_MAPPINGS: Dict[str, Dict[str, List[str]]] = {
    "supabase": {
        "service_role_key": ["SUPABASE_SERVICE_ROLE_KEY"],
        "anon_key": ["SUPABASE_ANON_KEY"],
        "url": ["SUPABASE_URL"],
    },
    "openai": {
        "api_key": ["OPENAI_API_KEY"],
    },
    "gemini": {
        "api_key": ["GEMINI_API_KEY", "GOOGLE_GEMINI_API_KEY"],
    },
    "anthropic": {
        "api_key": ["ANTHROPIC_API_KEY"],
    },
    "gh": {
        "api_key": ["GH_API_KEY", "GITHUB_TOKEN"],
    },
    "github": {
        "token": ["GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"],
    },
    "notion": {
        "notion_token": ["NOTION_TOKEN"],
    },
}


class SecretManagerError(Exception):
    """Base exception for secret manager errors."""
    pass


class SecretNotFoundError(SecretManagerError):
    """Raised when a secret is not found."""
    pass


class InvalidPasswordError(SecretManagerError):
    """Raised when master password is incorrect."""
    pass


class SecretManager:
    """
    Manages encrypted secret storage using AES-256-GCM.
    
    Secrets are stored in .agent/secrets/ directory with:
    - config.json: Salt and metadata
    - {service}.json: Encrypted secrets per service
    """
    
    def __init__(self, secrets_dir: Optional[Path] = None):
        """Initialize SecretManager with secrets directory."""
        if secrets_dir is None:
            # Default to .agent/secrets/ relative to repo root
            from agent.core.config import config
            secrets_dir = config.agent_dir / "secrets"
        
        self.secrets_dir = Path(secrets_dir)
        self.config_file = self.secrets_dir / "config.json"
        self._master_key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
    
    def is_initialized(self) -> bool:
        """Check if secret management is initialized."""
        return self.config_file.exists()
    
    def is_unlocked(self) -> bool:
        """Check if the secret manager is unlocked (key in memory)."""
        return self._master_key is not None
    
    def initialize(self, master_password: str, force: bool = False) -> None:
        """
        Initialize secret storage with master password.
        
        Creates the secrets directory, generates salt, and stores metadata.
        """
        if self.is_initialized() and not force:
             raise SecretManagerError("Secret manager already initialized")

        # Safety Check: Orphaned Secrets
        # If config doesn't exist (not initialized) but OTHER json files do, we are about to orphan them.
        if not self.is_initialized() and self.secrets_dir.exists():
             existing_files = [f for f in self.secrets_dir.glob("*.json") if f.name != "config.json"]
             if existing_files and not force:
                 raise SecretManagerError(
                     f"Found existing secret files ({len(existing_files)}). "
                     "Initializing now will make them permanently unreadable. "
                     "Use --force to overwrite them, or 'agent secret rotate-key' to change password."
                 )
        
        # Create secrets directory with restricted permissions
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.secrets_dir, stat.S_IRWXU)  # 700
        
        # Generate salt
        self._salt = os.urandom(SALT_LENGTH)
        
        # Derive key
        self._master_key = self._derive_key(master_password, self._salt)
        
        # Store config with salt (encoded as base64)
        config_data = {
            "salt": base64.b64encode(self._salt).decode("utf-8"),
            "created_at": datetime.now(UTC).isoformat(),
            "version": "1.0",
            "pbkdf2_iterations": PBKDF2_ITERATIONS,
        }
        
        self._save_json(self.config_file, config_data)
        
        # Create .gitignore
        gitignore_path = self.secrets_dir / ".gitignore"
        gitignore_content = """# Never commit secrets
*.json
!.gitignore

# Backup files
*.bak
*.backup
*.tmp
"""
        gitignore_path.write_text(gitignore_content)
        
        self._log_operation("init", "system", "config", "success")
        logger.info("Secret manager initialized successfully")

    def change_password(self, old_password: str, new_password: str) -> None:
        """
        Rotate master password: decrypt all secrets, re-encrypt with new key.
        Atomic operation with rollback support.
        """
        import shutil
        
        # 1. Verify and Unlock
        self.unlock(old_password)
        
        # 2. Derive NEW key
        new_salt = os.urandom(SALT_LENGTH)
        new_master_key = self._derive_key(new_password, new_salt)
        
        # 3. Create Backup
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        backup_dir = self.secrets_dir.parent / "backups" / f"secrets_{timestamp}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(self.secrets_dir, backup_dir)
        
        # 4. Prepare Temp Directory
        temp_dir = self.secrets_dir.with_suffix(".rotation_tmp")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(mode=0o700)
        
        try:
            # 5. Load and Re-encrypt All Secrets
            # Copy config first, but we will update it later
            temp_config = temp_dir / "config.json"
            
            # Re-encrypt Service Files
            aesgcm_new = AESGCM(new_master_key)
            
            for service_file in self.secrets_dir.glob("*.json"):
                if service_file.name == "config.json":
                    continue
                
                # Decrypt old
                secrets = self._load_service_secrets(service_file.stem)
                new_secrets = {}
                
                for key, encrypted_val in secrets.items():
                    # Decrypt with old key (self._master_key is currently old key)
                    plaintext = self._decrypt_value(encrypted_val)
                    
                    # Encrypt with NEW key
                    nonce = os.urandom(NONCE_LENGTH)
                    ciphertext = aesgcm_new.encrypt(nonce, plaintext.encode("utf-8"), None)
                    
                    new_secrets[key] = {
                        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                        "nonce": base64.b64encode(nonce).decode("utf-8"),
                        "updated_at": datetime.now(UTC).isoformat()
                    }
                    
                # Save to temp
                self._save_json(temp_dir / service_file.name, new_secrets)

            # 6. Update Config in Temp
            config_data = {
                "salt": base64.b64encode(new_salt).decode("utf-8"),
                "created_at": datetime.now(UTC).isoformat(),
                "version": "1.0",
                "pbkdf2_iterations": PBKDF2_ITERATIONS,
            }
            self._save_json(temp_config, config_data)
            
            # 7. Atomic Swap
            # We can't rename over non-empty dir easily cross-platform, but on POSIX os.replace is atomic
            # For safety, we'll swap paths.
            
            # Implementation detail: Move 'secrets' to 'secrets_old', move 'temp' to 'secrets', delete 'secrets_old'
            old_secrets_path = self.secrets_dir.with_suffix(".old")
            if old_secrets_path.exists():
                shutil.rmtree(old_secrets_path)
                
            os.rename(self.secrets_dir, old_secrets_path)
            os.rename(temp_dir, self.secrets_dir)
            shutil.rmtree(old_secrets_path)
            
            # 8. Update In-Memory State
            self._salt = new_salt
            self._master_key = new_master_key
            
            self._log_operation("rotate_key", "system", "all", "success")
            
        except Exception as e:
            # Rollback is implicit if we failed before rename: existing secrets_dir is untouched.
            # If we failed DURING rename (scary), we might need manual intervention, but we have backup.
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise SecretManagerError(f"Rotation failed: {e}. Backup at {backup_dir}")

    def unlock(self, master_password: str) -> None:
        """
        Unlock the secret manager with master password.
        
        Loads salt from config and derives key.
        """
        if not self.is_initialized():
            raise SecretManagerError(
                "Secret manager not initialized. Run 'agent secret init' first."
            )
        
        # Load config and salt
        config_data = self._load_json(self.config_file)
        self._salt = base64.b64decode(config_data["salt"])
        
        # Derive key
        self._master_key = self._derive_key(master_password, self._salt)
        
        # Verify password by trying to load and decrypt existing secrets
        # If there are no secrets yet, we can't verify, so we trust the user
        for service_file in self.secrets_dir.glob("*.json"):
            if service_file.name == "config.json":
                continue
            try:
                secrets = self._load_service_secrets(service_file.stem)
                # verify by attempting to decrypt first available secret
                if secrets:
                    first_key = next(iter(secrets))
                    self._decrypt_value(secrets[first_key])
                    break  # Password is correct
            except Exception:
                self._master_key = None
                raise InvalidPasswordError("Incorrect master password")
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2-HMAC-SHA256."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))
    
    def _encrypt_value(self, plaintext: str) -> Dict[str, str]:
        """
        Encrypt value using AES-256-GCM.
        
        Returns dict with ciphertext, nonce, and tag (combined in
        ciphertext for AESGCM).
        """
        if not self._master_key:
            raise SecretManagerError("Secret manager not unlocked")
        
        nonce = os.urandom(NONCE_LENGTH)
        aesgcm = AESGCM(self._master_key)
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
        }
    
    def _decrypt_value(self, encrypted: Dict[str, str]) -> str:
        """Decrypt value using AES-256-GCM."""
        if not self._master_key:
            raise SecretManagerError("Secret manager not unlocked")
        
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        nonce = base64.b64decode(encrypted["nonce"])
        
        aesgcm = AESGCM(self._master_key)
        
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception as e:
            raise InvalidPasswordError(f"Decryption failed: {e}")
    
    def _get_service_file(self, service: str) -> Path:
        """Get path to service secrets file."""
        return self.secrets_dir / f"{service}.json"
    
    def _load_service_secrets(self, service: str) -> Dict[str, Dict[str, str]]:
        """Load encrypted secrets for a service."""
        service_file = self._get_service_file(service)
        if not service_file.exists():
            return {}
        return self._load_json(service_file)

    def _save_service_secrets(
        self, service: str, secrets: Dict[str, Dict[str, str]]
    ) -> None:
        """Save encrypted secrets for a service."""
        service_file = self._get_service_file(service)
        self._save_json(service_file, secrets)
    
    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON file safely."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Save JSON file atomically with restricted permissions."""
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    
    def set_secret(self, service: str, key: str, value: str) -> None:
        """
        Store encrypted secret.
        
        Args:
            service: Service name (e.g., 'openai', 'supabase')
            key: Secret key name (e.g., 'api_key')
            value: Secret value to encrypt
        """
        if not self.is_unlocked():
            raise SecretManagerError("Secret manager not unlocked")
        
        secrets = self._load_service_secrets(service)
        secrets[key] = self._encrypt_value(value)
        secrets[key]["updated_at"] = datetime.now(UTC).isoformat()
        
        self._save_service_secrets(service, secrets)
        self._log_operation("set", service, key, "success")
    
    def has_secret(self, service: str, key: str) -> bool:
        """
        Check if secret exists in secure storage (no fallback).
        """
        if not self.is_unlocked():
            return False
        
        secrets = self._load_service_secrets(service)
        return key in secrets
    
    def get_secret(self, service: str, key: str) -> Optional[str]:
        """
        Retrieve and decrypt secret.
        
        Returns None if secret not found. Falls back to environment variable
        if configured.
        """
        # Try secret manager first
        if self.is_unlocked():
            secrets = self._load_service_secrets(service)
            if key in secrets:
                try:
                    value = self._decrypt_value(secrets[key])
                    self._log_operation("get", service, key, "success")
                    return value
                except Exception as e:
                    logger.warning(f"Failed to decrypt secret {service}.{key}: {e}")
        
        # Fallback to environment variable
        if service in SERVICE_ENV_MAPPINGS and key in SERVICE_ENV_MAPPINGS[service]:
            for env_var in SERVICE_ENV_MAPPINGS[service][key]:
                value = os.getenv(env_var)
                if value:
                    self._log_operation("get", service, key, "fallback_env")
                    return value
        
        return None
    
    def list_secrets(self, service: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        List all secrets (masked).
        
        Returns structure: {service: {key: "***masked***"}}
        """
        result: Dict[str, Dict[str, str]] = {}
        
        if service:
            services = [service]
        else:
            services = [
                f.stem for f in self.secrets_dir.glob("*.json")
                if f.name != "config.json"
            ]
        
        for svc in services:
            secrets = self._load_service_secrets(svc)
            if secrets:
                result[svc] = {}
                for key in secrets:
                    result[svc][key] = "***masked***"
        
        return result
    
    def delete_secret(self, service: str, key: str) -> bool:
        """
        Delete a secret.
        
        Returns True if deleted, False if not found.
        """
        if not self.is_unlocked():
            raise SecretManagerError("Secret manager not unlocked")
        
        secrets = self._load_service_secrets(service)
        if key not in secrets:
            return False
        
        del secrets[key]
        
        if secrets:
            self._save_service_secrets(service, secrets)
        else:
            # Remove empty service file
            service_file = self._get_service_file(service)
            if service_file.exists():
                service_file.unlink()
        
        self._log_operation("delete", service, key, "success")
        return True
    
    def import_from_env(self, service: str) -> int:
        """
        Import secrets from environment variables.
        
        Returns count of imported secrets.
        """
        if not self.is_unlocked():
            raise SecretManagerError("Secret manager not unlocked")
        
        if service not in SERVICE_ENV_MAPPINGS:
            raise SecretManagerError(f"Unknown service: {service}")
        
        imported = 0
        for key, env_vars in SERVICE_ENV_MAPPINGS[service].items():
            for env_var in env_vars:
                value = os.getenv(env_var)
                if value:
                    self.set_secret(service, key, value)
                    imported += 1
                    break  # Only import first found env var for this key
        
        return imported
    
    def export_to_env(self, service: str) -> Dict[str, str]:
        """
        Export secrets as environment variable format.
        
        Returns dict of {ENV_VAR_NAME: value}.
        """
        if not self.is_unlocked():
            raise SecretManagerError("Secret manager not unlocked")
        
        if service not in SERVICE_ENV_MAPPINGS:
            raise SecretManagerError(f"Unknown service: {service}")
        
        result: Dict[str, str] = {}
        secrets = self._load_service_secrets(service)
        
        for key, env_vars in SERVICE_ENV_MAPPINGS[service].items():
            if key in secrets:
                value = self._decrypt_value(secrets[key])
                # Use first env var name as the export name
                result[env_vars[0]] = value
        
        return result
    
    def _log_operation(
        self,
        operation: str,
        service: str,
        key: str,
        status: str
    ) -> None:
        """Log secret management operation for SOC2 compliance."""
        # Never log secret values
        audit_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": operation,
            "service": service,
            "key": key,
            "status": status,
            "component": "secret_manager",
        }
        logger.info(f"SECRET_OP: {json.dumps(audit_entry)}")


# Global singleton instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """
    Get or create the global SecretManager instance.
    
    Automatically attempts to unlock using:
    1. System Keyring (secure local storage)
    2. AGENT_MASTER_KEY (CI/CD override)
    """
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
        
        # 1. Try Keyring (Secure Local)
        if _secret_manager.is_initialized():
            try:
                import keyring
                # Use 'agent-cli' as service name, 'master_key' as username
                stored_key = keyring.get_password("agent-cli", "master_key")
                if stored_key:
                    try:
                        _secret_manager.unlock(stored_key)
                        logger.info("Secret manager auto-unlocked via Keyring")
                        return _secret_manager
                    except Exception as e:
                        logger.warning(f"Keyring key invalid: {e}")
            except ImportError:
                pass  # Keyring library not available
            except Exception as e:
                logger.warning(f"Keyring access failed: {e}")

        # 2. Try Env Var (CI/CD)
        master_key = os.getenv("AGENT_MASTER_KEY")
        if master_key and _secret_manager.is_initialized() and not _secret_manager.is_unlocked():
            try:
                _secret_manager.unlock(master_key)
                logger.info("Secret manager auto-unlocked via AGENT_MASTER_KEY")
            except Exception as e:
                logger.warning(f"Failed to auto-unlock secret manager: {e}")
                
    return _secret_manager


def get_secret(key: str, service: Optional[str] = None, strict: bool = False) -> Optional[str]:
    """
    Convenience function to get a secret.
    
    Args:
        key: Secret key name
        service: Service name (e.g., 'gemini', 'openai')
        strict: If True, raises error when secrets are locked. 
                If False (default), allows fallback to env vars during initialization.
    
    Tries secret manager first. If secrets are initialized but locked:
    - strict=True: Raises error (used during AI operations)
    - strict=False: Falls back to env vars (used during module initialization)
    """
    manager = get_secret_manager()
    
    # If secrets are initialized but locked, handle based on strict mode
    if service and manager.is_initialized() and not manager.is_unlocked():
        if strict:
            from rich.console import Console
            console = Console()
            console.print(
                "[bold red]❌ Secret manager is locked.[/bold red]\n"
                "[yellow]Run 'agent secret login' to unlock secrets.[/yellow]"
            )
            raise SecretManagerError(
                f"Secret manager is locked. Run 'agent secret login' to access {service} secrets."
            )
        # In non-strict mode, check if the secret file exists before falling
        # through to env vars.  If the secret is on disk we can still confirm
        # it's present (without decrypting) and try an automatic unlock.
        service_file = manager._get_service_file(service)
        if service_file.exists():
            try:
                data = manager._load_json(service_file)
                if key in data:
                    # Secret is stored — fall through to env var lookup
                    # but don't warn about missing credentials.
                    pass
            except Exception:
                pass
    
    if service and manager.is_initialized() and manager.is_unlocked():
        value = manager.get_secret(service, key)
        if value:
            return value
    
    # Fallback to environment variable using mapping
    if (
        service
        and service in SERVICE_ENV_MAPPINGS
        and key in SERVICE_ENV_MAPPINGS[service]
    ):
        for env_var in SERVICE_ENV_MAPPINGS[service][key]:
            value = os.getenv(env_var)
            if value:
                return value

    # Direct fallback (legacy or unmapped)
    return os.getenv(key)
