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
    # Check keys based on the configured LLM_PROVIDER
    provider = LLM_PROVIDER.lower()
    
    # Map provider to list of acceptable keys (any one will do)
    provider_key_map = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "gh": ["GH_API_KEY", "GITHUB_TOKEN"]
    }
    
    # Default to OpenAI if unknown, or just check nothing if provider is 'local' etc.
    target_keys = provider_key_map.get(provider, ["OPENAI_API_KEY"])
    
    secret_manager = get_secret_manager()
    missing_keys = []
    
    # We only need ONE valid key from the list for the provider
    found_any = False
    
    for key in target_keys:
        # Step A: Check Env Var
        if os.getenv(key):
            found_any = True
            break
            
        # Step B: Check Secret Store
        # Map: OPENAI_API_KEY -> service='openai', key='api_key'
        # Heuristic: Provider is 'openai', key is 'api_key'
        # Basic mapping for now
        service_name = provider
        secret_name = "api_key"
        
        # Verify mapping logic for known keys if needed, but 'api_key' is the standard constraint
        if secret_manager.get_secret(service_name, secret_name):
            found_any = True
            break
            
    if not found_any:
        # Report the primary key name as missing
        missing_keys.append(target_keys[0])
        
    if missing_keys:
        logger.warning(f"AUDIT: Missing critical credentials for provider '{provider}': {missing_keys}")
        raise MissingCredentialsError(missing_keys)
