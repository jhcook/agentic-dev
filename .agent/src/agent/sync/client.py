
import os
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

from typing import Optional
from supabase import create_client, Client
from agent.core.secrets import get_secret

def get_supabase_client(verbose: bool = False) -> Optional[Client]:
    """
    Initializes and returns a Supabase client.
    
    Retrieves credentials from Agent Secret Manager, environment variables, or sync.yaml.
    """
    # 1. Try Secrets / Env Vars (via secrets module)
    url = get_secret("url", "supabase")
    key = get_secret("service_role_key", "supabase") or get_secret("anon_key", "supabase")

    if verbose:
        print(f"Debug: Initial checks - URL found: {bool(url)}, Key found: {bool(key)}")

    # 2. Fallback: Parse .agent/etc/sync.yaml for URL
    if not url:
        try:
            from agent.core.config import config
            sync_config = config.load_yaml(config.etc_dir / "sync.yaml")
            url = sync_config.get("supabase_url")
            if verbose and url:
                print(f"Debug: Found URL in sync.yaml: {url}")
        except Exception as e:
            if verbose:
                print(f"Debug: Failed to read sync.yaml: {e}")

    if not url or not key:
        if verbose:
            if not url: print("Debug: URL missing. Checked secrets, env vars, and sync.yaml.")
            if not key: print("Debug: Key missing. Checked secrets and env vars.")
        return None

    try:
        if verbose:
            print("Debug: Attempting to create Supabase client...")
        return create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        return None
