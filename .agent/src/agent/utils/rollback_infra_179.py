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
Rollback utility for INFRA-179: Public Symbol Rename Detection.

This script disables the rename detection gate by commenting out its invocation
in the runbook validation logic. This is a safe, additive rollback.
"""
import sys
from pathlib import Path

def main():
    """Comment out the rename check invocation in runbook_gates.py."""
    # Use relative path from project root
    target_path = Path(".agent/src/agent/commands/runbook_gates.py")
    
    if not target_path.exists():
        print(f"[ERROR] Target file not found: {target_path}")
        sys.exit(1)

    content = target_path.read_text()
    
    # The specific line added during implementation
    target_line = "    check_api_surface_renames("
    
    if target_line not in content:
        print("[INFO] INFRA-179 gate invocation not found or already disabled.")
        return

    lines = content.splitlines()
    new_lines = []
    modified = False

    for line in lines:
        if target_line in line and not line.strip().startswith("#"):
            # Preserve leading indentation
            indent = line[:line.find(target_line)]
            new_lines.append(f"{indent}# {line.lstrip()}")
            modified = True
        else:
            new_lines.append(line)

    if modified:
        target_path.write_text("\n".join(new_lines) + "\n")
        print("[SUCCESS] INFRA-179: Public Symbol Rename Detection gate has been disabled.")
    else:
        print("[INFO] No active invocation found to disable.")

if __name__ == "__main__":
    main()
