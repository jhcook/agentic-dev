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

"""Contingency utility to revert INFRA-171 migration changes and cleanup implementation artifacts."""

import subprocess
import sys
from pathlib import Path

# Files to be reverted to HEAD state
REVERT_TARGETS = [
    ".agent/src",
    ".agent/tests",
    ".agent/pyproject.toml",
    ".agent/rules/400-lean-code.mdc",
    ".agent/src/agent/core/ai/prompts.py"
]

# Temporary artifacts to delete
CLEANUP_TARGETS = [
    ".agent/scripts/migrate_tests.py",
    ".agent/src/agent/core/governance/migration_audit_tool.py",
    ".agent/src/agent/core/governance/test_metrics.py",
    ".agent/docs/development/testing-standards.md",
    ".agent/tests/agent/core/governance/test_migration_verification.py"
]

def run_rollback():
    """Executes git checkout and removes implementation files."""
    print("Starting rollback of INFRA-171...")

    # 1. Git checkout revert
    try:
        subprocess.run(["git", "checkout", "HEAD", "--"] + REVERT_TARGETS, check=True)
        print("✅ Successfully restored src, tests, and configuration from Git HEAD.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during git checkout: {e}")
        sys.exit(1)

    # 2. Cleanup artifacts
    for target in CLEANUP_TARGETS:
        path = Path(target)
        if path.exists():
            try:
                if path.is_file():
                    path.unlink()
                    print(f"🗑️ Removed artifact: {target}")
            except OSError as e:
                print(f"⚠️ Failed to remove {target}: {e}")

    print("Rollback complete. System state restored.")

if __name__ == "__main__":
    run_rollback()
