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

from pathlib import Path

class Config:
    def __init__(self):
        # Locate the root of the repostory.
        # Assuming this file is in .agent/src/agent/core/config.py
        # We need to go up 4 levels to get to the repo root from .agent/src/agent/core
        # But wait, .agent is at the root.
        # .agent/src/agent/core -> up 1 -> agent/src/agent -> up 2 -> agent/src -> up 3 -> .agent -> up 4 -> repo root?
        # Let's rely on finding .agent directory.
        
        self.repo_root = self._find_repo_root()
        self.agent_dir = self.repo_root / ".agent"
        self.cache_dir = self.agent_dir / "cache"
        self.stories_dir = self.cache_dir / "stories"
        self.plans_dir = self.cache_dir / "plans"
        self.runbooks_dir = self.cache_dir / "runbooks"
        self.adrs_dir = self.agent_dir / "adrs"
        self.templates_dir = self.agent_dir / "templates"
        self.rules_dir = self.agent_dir / "rules"
        self.instructions_dir = self.agent_dir / "instructions"
        self.etc_dir = self.agent_dir / "etc"

    def _find_repo_root(self) -> Path:
        """Finds the git repository root."""
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / ".agent").exists():
                return parent
            if (parent / ".git").exists():
                return parent
        # Fallback
        return Path.cwd()

# Global config instance
config = Config()
