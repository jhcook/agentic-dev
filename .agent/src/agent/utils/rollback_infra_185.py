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

"""Rollback script for INFRA-185.

Removes additive components introduced for the Claude Bedrock provider.
"""
import os
from pathlib import Path

def rollback() -> None:
    """Remove additive files and list registry locations requiring manual revert."""
    # This script is located at .agent/src/agent/utils/rollback_infra_185.py
    src_root = Path(__file__).resolve().parent.parent.parent
    project_root = src_root.parent # .agent/
    
    files_to_delete = [
        src_root / "agent/core/ai/providers/claude.py",
        project_root / "tests/core/ai/providers/test_claude_provider.py",
        project_root / "docs/providers/claude.md"
    ]
    
    print("--- INFRA-185 Rollback Started ---")
    
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"[DELETED] {f}")
        else:
            print(f"[SKIP] {f} (not found)")

    print("\nManual Reversion Required in the following core framework files:")
    print("1. .agent/pyproject.toml: Revert 'anthropic[bedrock]' to 'anthropic'")
    print("2. .agent/src/agent/core/ai/providers/__init__.py: Remove 'claude' registration from PROVIDER_MAP")
    print("3. .agent/src/agent/core/ai/service.py: Remove provider dispatch cases and model mappings")
    print("4. .agent/src/agent/core/config.py: Remove 'claude' from enabled provider logic")
    print("5. .agent/etc/router.yaml: Remove Bedrock model definitions")
    print("6. .agent/etc/agent.yaml: Remove 'claude' configuration block")
    print("\n--- Rollback Guidance Complete ---")

if __name__ == '__main__':
    rollback()
