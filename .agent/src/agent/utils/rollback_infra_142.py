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
Rollback utility for INFRA-142 tool migration.

Provides automated guidance and verification for reverting the tool registry
to legacy implementations if the new search/git modules encounter issues.
"""

import sys
from pathlib import Path

def check_rollback_readiness() -> bool:
    """
    Verifies that legacy tools are still available for fallback.
    """
    legacy_path = Path(".agent/src/agent/core/adk/tools.py")
    if not legacy_path.exists():
        print("[ERROR] Legacy tools.py missing. Rollback impossible.")
        return False
    print("[SUCCESS] Legacy fallback tools are present.")
    return True

def print_rollback_instructions():
    """
    Outputs manual steps required to restore legacy search logic.
    """
    print("\n--- INFRA-142 ROLLBACK INSTRUCTIONS ---")
    print("1. Open .agent/src/agent/tools/__init__.py")
    print("2. Locate 'register_domain_tools' function.")
    print("3. Change the filesystem specs to use 'agent.core.adk.tools.read_file' instead of 'filesystem.read_file'.")
    print("4. Restart the agent session to reload the ToolRegistry.")

if __name__ == "__main__":
    if check_rollback_readiness():
        print_rollback_instructions()
        sys.exit(0)
    sys.exit(1)