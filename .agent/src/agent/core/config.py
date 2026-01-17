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
from pathlib import Path

class Config:
    def __init__(self):
        # file is in .agent/src/agent/core/config.py
        # .parents[4] resolves to the repo root (containing .agent)
        self.repo_root = Path(__file__).parents[4]
        
        self.agent_dir = self.repo_root / ".agent"
        self.src_dir = self.agent_dir / "src"
        self.templates_dir = self.agent_dir / "templates"
        self.etc_dir = self.agent_dir / "etc"
        self.rules_dir = self.agent_dir / "rules"
        self.instructions_dir = self.agent_dir / "instructions"
        self.cache_dir = self.agent_dir / "cache"
        self.adrs_dir = self.agent_dir / "adrs"
        self.logs_dir = self.agent_dir / "logs"
        self.agent_dir = self.repo_root / ".agent"

        self.stories_dir = self.cache_dir / "stories"
        self.plans_dir = self.cache_dir / "plans"
        self.runbooks_dir = self.cache_dir / "runbooks"
        
config = Config()


from typing import Dict, List, Optional

def get_provider_config(provider_name: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Retrieve the configuration for a given provider.
    """
    config_map = {
        "gh": {"api_key": os.getenv("GH_API_KEY")},
        "openai": {"api_key": os.getenv("OPENAI_API_KEY")},
        "gemini": {"api_key": os.getenv("GEMINI_API_KEY")},
    }
    return config_map.get(provider_name.lower())

def get_valid_providers() -> List[str]:
    """
    Dynamically loads valid providers from the configuration keys.
    """
    # Create a temporary map to extract keys
    # In a real dynamic system, this might scan installed plugins or config files
    # For now, we reuse the source of truth in get_provider_config logic
    # or better, define the supported providers constant if we can't inspect the function easily.
    # To keep it simple and dynamic-ish:
    return ["gh", "openai", "gemini"]