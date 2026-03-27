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
Rollback utility for INFRA-143.

This script reverts the tool exports in .agent/src/agent/tools/__init__.py to point
back to the original implementations in scattered modules.
"""

import os
from pathlib import Path

def rollback_registry_imports():
    """Revert registry imports to legacy scattered implementations."""
    init_file = Path(".agent/src/agent/tools/__init__.py")
    if not init_file.exists():
        print(f"[ERROR] Entry point {init_file} not found.")
        return

    print("[INFO] Reverting ToolRegistry imports to legacy scattered modules...")
    
    # Note: Search strings match the consolidated exports implemented in Step 2
    content = init_file.read_text()

    # Revert Project tools
    content = content.replace(
        "from .project import match_story, read_story, read_runbook, list_stories, list_workflows, fix_story, list_capabilities",
        "from agent.commands.match import match_story\n# Legacy scattered implementations"
    )

    # Revert Knowledge tools
    content = content.replace(
        "from .knowledge import read_adr, read_journey, search_knowledge",
        "from agent.commands.adr import read_adr\nfrom agent.commands.journey import read_journey"
    )

    init_file.write_text(content)
    print("[SUCCESS] Rollback complete. Registry redirected to legacy tools.")

if __name__ == "__main__":
    rollback_registry_imports()
