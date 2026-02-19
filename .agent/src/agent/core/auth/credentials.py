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

import os
from typing import List

from agent.core.config import config, LLM_PROVIDER
from agent.core.secrets import get_secret_manager
from agent.core.auth.errors import MissingCredentialsError
import logging

logger = logging.getLogger(__name__)

def validate_credentials(check_llm: bool = True) -> None:
    """
    Validates that necessary credentials are present in either environment variables
    or the secret store.
    
    Args:
        check_llm: If True, validates LLM provider specific keys.
    
    Raises:
        MissingCredentialsError: If any required credential is missing from both sources.
    """
    if not check_llm:
        return

    # 1. Determine active providers/keys to check
    # Check keys based on the configured LLM_PROVIDER or runtime override
    from agent.core.ai import ai_service
    provider = (ai_service.provider or LLM_PROVIDER).lower()
    
    # Map provider to list of acceptable keys (any one will do)
    provider_key_map = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "gh": ["GH_API_KEY", "GITHUB_TOKEN"],
        "vertex": ["GOOGLE_CLOUD_PROJECT"],
    }
    
    # Default to OpenAI if unknown, or just check nothing if provider is 'local' etc.
    target_keys = provider_key_map.get(provider, ["OPENAI_API_KEY"])
    
    secret_manager = get_secret_manager()
    missing_keys = []
    
    # We only need ONE valid key from the list for the provider
    found_any = False
    
    for key in target_keys:
        # Step A: Check Env Var (takes precedence)
        if os.getenv(key):
            found_any = True
            break
            
        # Step B: Check Secret Store
        # Try unlocked access first, then fall back to file existence check.
        # This avoids false "missing credential" errors when the store is
        # locked but the secret is stored.
        service_name = provider
        secret_name = "api_key"
        
        if secret_manager.is_unlocked():
            if secret_manager.get_secret(service_name, secret_name):
                found_any = True
                break
        elif secret_manager.is_initialized():
            # Store is locked — check if the service file contains the key
            # without requiring the master password.
            service_file = secret_manager._get_service_file(service_name)
            if service_file.exists():
                try:
                    data = secret_manager._load_json(service_file)
                    if secret_name in data:
                        # Found validation data, but store is locked.
                        # We cannot use this credential.
                        from agent.core.secrets import SecretManagerError
                        raise SecretManagerError(
                            f"Credentials for '{provider}' exist but Secret Manager is locked. "
                            "Run 'agent secret login' to unlock."
                        )
                except ImportError:
                    raise
                except SecretManagerError:
                    raise
                except Exception:
                    pass
            
    if not found_any:
        # Report the primary key name as missing
        missing_keys.append(target_keys[0])
        
    if missing_keys:
        logger.warning(f"AUDIT: Missing critical credentials for provider '{provider}': {missing_keys}")
        raise MissingCredentialsError(missing_keys)

