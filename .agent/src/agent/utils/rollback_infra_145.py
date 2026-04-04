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

"""rollback_infra_145 module."""

import os
import sys

def run_rollback():
    """
    Rollback script for INFRA-145.
    Sets the environment to bypass the unified ToolRegistry and use legacy logic.
    """
    print("--- INFRA-145 Rollback Tool ---")
    print("Target: Revert Console and Voice adapters to direct tool instantiation.")
    
    # Setting the environment variable for the current process and providing instructions
    os.environ["USE_UNIFIED_REGISTRY"] = "false"
    
    print("\n[SUCCESS] USE_UNIFIED_REGISTRY has been set to 'false' in the current execution context.")
    print("\n[ACTION REQUIRED]:")
    print("To apply this globally, update your environment configuration (e.g., .env or system vars):")
    print("    export USE_UNIFIED_REGISTRY=false")
    print("Then, restart the following services:")
    print("    - Console TUI (agent.tui.session)")
    print("    - Voice Orchestrator (backend.voice.orchestrator)")

if __name__ == "__main__":
    run_rollback()
