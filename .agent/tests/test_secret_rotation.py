
import os
import shutil
import pytest
from pathlib import Path
from agent.core.secrets import SecretManager, SecretManagerError, InvalidPasswordError

@pytest.fixture
def secret_manager(tmp_path):
    secrets_dir = tmp_path / "secrets"
    return SecretManager(secrets_dir=secrets_dir)

def test_initialize_and_rotate(secret_manager):
    # 1. Initialize logic
    password = "OldPassword123!"
    secret_manager.initialize(password)
    
    # 2. Add some secrets
    secret_manager.unlock(password)
    secret_manager.set_secret("test", "key", "secret_value")
    
    assert secret_manager.get_secret("test", "key") == "secret_value"
    
    # 3. Rotate Password
    new_password = "NewPassword456!"
    secret_manager.change_password(password, new_password)
    
    # 4. Verification
    # Old password should fail
    with pytest.raises(InvalidPasswordError):
        secret_manager.unlock(password)
        
    # New password should work
    secret_manager.unlock(new_password)
    assert secret_manager.get_secret("test", "key") == "secret_value"

def test_init_safety_guard(secret_manager, tmp_path):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    
    # Create an orphan secret file
    (secrets_dir / "orphan.json").write_text("{}")
    
    # Init should fail without force
    with pytest.raises(SecretManagerError, match="Found existing secret files"):
        secret_manager.initialize("Password123!")
        
    # Init should succeed with force
    secret_manager.initialize("Password123!", force=True)
    assert (secrets_dir / "config.json").exists()

def test_chaos_interruption_backup(secret_manager):
    """
    Simulate interruption by manually triggering a failure during rotation 
    and ensuring backup exists / state is recoverable.
    """
    password = "Pass1!"
    secret_manager.initialize(password)
    secret_manager.unlock(password)
    secret_manager.set_secret("svc", "k", "v")
    
    # Mock _save_json to raise exception halfway through
    original_save = secret_manager._save_json
    
    def fail_on_save(*args, **kwargs):
        if "config.json" in str(args[0]): # Fail on config save (late stage)
            raise RuntimeError("Chaos Monkey!")
        original_save(*args, **kwargs)
        
    secret_manager._save_json = fail_on_save
    
    with pytest.raises(SecretManagerError, match="Rotation failed"):
        secret_manager.change_password(password, "Pass2!")
        
    # Check if backup exists (path logic from implementation)
    # The implementation creates backup at secrets_dir.parent / "backups" / ...
    
    backups_dir = secret_manager.secrets_dir.parent / "backups"
    assert backups_dir.exists()
    assert len(list(backups_dir.glob("secrets_*"))) > 0
    
    # Check that original secrets are still valid (rollback implicit or manual recovery needed?)
    # In our implementation, we raise Error but don't auto-restore from backup if rename hasn't happened yet.
    # Since we failed BEFORE atomic swap, the original directory should be untouched.
    
    secret_manager._save_json = original_save # Restore
    secret_manager.unlock(password)
    assert secret_manager.get_secret("svc", "k") == "v"
