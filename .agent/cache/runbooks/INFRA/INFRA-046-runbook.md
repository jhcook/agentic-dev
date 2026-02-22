## STORY-ID: INFRA-046: Secure Secret Rotation

## State

ACCEPTED

## Goal Description

Implement a safe and secure secret rotation mechanism for the Agent CLI, preventing accidental data loss during re-initialization and allowing users to change their master password without losing access to their stored credentials.

## Panel Review Findings

- **@Architect**: The proposal to use temporary files and atomic operations for rotation is sound and necessary. We should consider using a database transaction if the number of secrets becomes very large in the future. The impact analysis seems reasonable.
- **@Security**: The focus on preventing plain-text storage of the password and the requirement for password strength validation are crucial. We need to ensure proper sanitization of password input to prevent command injection. Consider adding salt to key derivation.
- **@QA**: The test strategy covers the major areas but needs more detail, especially around failure injection during rotation. We need to test for various interrupt signals and disk space issues.
- **@Docs**: The user-facing documentation needs to clearly explain the data backup and recovery mechanisms in case of failure. The error messages also need to be well-documented.
- **@Compliance**: We need to ensure that the secret rotation process complies with any relevant data protection regulations (e.g., GDPR). Password complexity rules might be necessary. Ensure the backup complies.
- **@Observability**: We should add logging and metrics to track the success/failure of secret rotations, including the time taken and any errors encountered. These need to avoid leaking sensitive information.

## Implementation Steps

### agent.core.secrets

#### MODIFY agent.core.secrets/secret_manager.py

- Implement `SecretManager.change_password(old_password, new_password)` to handle the key rotation logic.
  - This method should:
    1. Validate `old_password` by unlocking.
    2. Generate a new master key from `new_password`.
    3. Create a temporary directory for re-encrypted secrets.
    4. Iterate through each existing secret file, decrypt it with the old key, and re-encrypt it with the new key into the temporary directory.
    5. Atomically replace the original `secrets/` directory with the temporary directory. This can be achieved using `os.rename`.
    6. Update the `config.json` file with the new master key metadata.
    7. Update the system keychain if applicable.
  - Handle potential exceptions during the process (e.g., incorrect password, file access errors).
  - Before start, BACKUP the current secrets directory with `shutil.copytree()`
  - Before switch using `os.rename`, BACKUP the `config.json`

```python
    def change_password(self, old_password: str, new_password: str) -> None:
        """
        Rotate master password: decrypt all secrets, re-encrypt with new key.
        Atomic operation with rollback support.
        """
        # 1. Verify and Unlock
        self.unlock(old_password)
        
        # 2. Derive NEW key
        new_salt = os.urandom(SALT_LENGTH)
        new_master_key = self._derive_key(new_password, new_salt)
        
        # 3. Create Backup
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
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
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                # Save to temp
                self._save_json(temp_dir / service_file.name, new_secrets)

            # 6. Update Config in Temp
            config_data = {
                "salt": base64.b64encode(new_salt).decode("utf-8"),
                "created_at": datetime.utcnow().isoformat(),
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
```

#### MODIFY agent.core.secrets/secret_manager.py

- Modify `initialize()` to prevent re-initialization if valid secret files exist.

```python
    def initialize(self, password: str, force: bool = False) -> None:
        """
        Initialize secret storage.
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
```

### agent.commands.secret

#### MODIFY agent.commands.secret/secret.py

- Update `init` command to handle the new safety check in `SecretManager.initialize()`.

```python
@app.command(name="init")
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing secrets")
):
    # ...
    try:
        manager.initialize(password, force=force)
    # ...
```

#### NEW agent.commands.secret/secret.py

- Implement `rotate-key` command using Typer.

```python
@app.command(name="rotate-key")
def rotate_key():
    """Rotate master password for all secrets."""
    manager = get_secret_manager()
    if not manager.is_initialized():
        console.print("[red]Not initialized.[/red]")
        raise typer.Exit(1)
        
    console.print("[bold]Rotating Master Key[/bold]")
    console.print("1. Enter CURRENT password to unlock.")
    old_pass = _prompt_password()
    
    try:
        manager.unlock(old_pass)
    except InvalidPasswordError:
        console.print("[red]Incorrect password.[/red]")
        raise typer.Exit(1)
        
    console.print("\n2. Enter NEW password.")
    new_pass = _prompt_password(confirm=True)
    if not _validate_password_strength(new_pass):
        raise typer.Exit(1)
        
    try:
        manager.change_password(old_pass, new_pass)
        console.print("[green]✅ Master key rotated successfully.[/green]")
        
        # Update Keychain if present
        try:
            import keyring
            keyring.set_password("agent-cli", "master_key", new_pass)
            console.print("[green]✅ System keychain updated.[/green]")
        except Exception:
            pass
            
    except Exception as e:
        console.print(f"[bold red]Rotation Failed: {e}[/bold red]")
        raise typer.Exit(1)
```

## Verification Plan

### Automated Tests

- [x] Unit test for `SecretManager.change_password` to verify correct re-encryption and password validation. Mock `os.listdir` to test different scenarios.
- [x] Integration test for `init` command safety check, mocking file system to simulate existing secret files.
- [x] Add a unit test to verify that the `_derive_key` function returns different keys for different passwords, and same key for same password + salt

### Manual Verification

- [x] Verify that `env -u VIRTUAL_ENV uv run agent secret init` fails without `--force` if secret files exist.
- [x] Verify that `env -u VIRTUAL_ENV uv run agent secret rotate-key` prompts for passwords and successfully rotates the key.
- [x] Verify that the old password no longer works after rotation, and the new password unlocks secrets.
- [x] **Chaos Testing**: Interrupt the `env -u VIRTUAL_ENV uv run agent secret rotate-key` process using `Ctrl+C` at various stages (e.g., during re-encryption, before atomic rename) and verify that the original secrets are preserved. Simulate disk full scenario and ensure graceful handling.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with new features and changes.
- [x] README.md updated with instructions on how to use the `rotate-key` command and explanations of the safety features.
- [ ] API Documentation updated (if applicable)

### Observability

- [x] Logs are structured and free of PII. Add log entries for:
  - Successful/failed initialization attempts.
  - Successful/failed key rotations.
  - Errors encountered during the rotation process.
- [x] Metrics added for new features (e.g., number of successful rotations, number of failed rotations).

### Testing

- [x] Unit tests passed
- [x] Integration tests passed
- [x] Manual verification passed

## Proposed Improvements (Opt-In)

- [ ] Implement a more robust password strength check using a dedicated library (e.g., `zxcvbn`).
- [ ] Add support for rotating secrets automatically on a schedule.
- [ ] Implement audit logging of all secret management operations.
