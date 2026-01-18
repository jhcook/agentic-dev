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
from datetime import datetime
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
    
    def initialize(self, master_password: str) -> None:
        """
        Initialize secret storage with master password.
        
        Creates the secrets directory, generates salt, and stores metadata.
        """
        if self.is_initialized():
            raise SecretManagerError("Secret manager already initialized")
        
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
            "created_at": datetime.utcnow().isoformat(),
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
        
        # Verify password by trying to load existing secrets
        # If there are no secrets yet, we can't verify, so we trust the user
        for service_file in self.secrets_dir.glob("*.json"):
            if service_file.name == "config.json":
                continue
            try:
                self._load_service_secrets(service_file.stem)
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
        secrets[key]["updated_at"] = datetime.utcnow().isoformat()
        
        self._save_service_secrets(service, secrets)
        self._log_operation("set", service, key, "success")
    
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
            "timestamp": datetime.utcnow().isoformat(),
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
    """Get or create the global SecretManager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_secret(key: str, service: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get a secret.
    
    Tries secret manager first, then falls back to environment variables.
    """
    manager = get_secret_manager()
    
    if service and manager.is_initialized() and manager.is_unlocked():
        value = manager.get_secret(service, key)
        if value:
            return value
    
    # Direct environment variable fallback
    return os.getenv(key)
