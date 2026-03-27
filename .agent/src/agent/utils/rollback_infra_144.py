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

"""Automated rollback script for INFRA-144."""

import os
from pathlib import Path

def rollback_infra_144():
    """Remove all new domain modules, tests, and documentation introduced in INFRA-144."""
    # Utility assumes it is run from the project root or via python -m
    base_dir = Path(__file__).parent.parent # .agent/src/agent/
    root_dir = base_dir.parent.parent       # ./
    
    targets = [
        base_dir / "tools/web.py",
        base_dir / "tools/testing.py",
        base_dir / "tools/deps.py",
        base_dir / "tools/context.py",
        root_dir / ".agent/tests/tools/test_web.py",
        root_dir / ".agent/tests/tools/test_testing.py",
        root_dir / ".agent/tests/tools/test_deps.py",
        root_dir / ".agent/tests/tools/test_context.py",
        root_dir / ".agent/docs/tools_reference.md",
    ]
    
    print("Initiating INFRA-144 Rollback...")
    
    for item in targets:
        if item.exists():
            try:
                item.unlink()
                print(f"  [REMOVED] {item}")
            except Exception as e:
                print(f"  [ERROR]   Could not delete {item}: {e}")
        else:
            print(f"  [SKIPPED] {item} (File not found)")
            
    print("\nRollback complete. Note: Revert exports in .agent/src/agent/tools/__init__.py manually.")

if __name__ == "__main__":
    rollback_infra_144()
