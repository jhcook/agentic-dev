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

"""Rollback script for INFRA-178.

Reverts the additive Gate 3.7 changes in guards.py and runbook_gates.py.
"""
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rollback_infra_178")

def rollback():
    """Removes Gate 3.7 logic and returns the pipeline to Gate 3.5 state."""
    root = Path(".")
    guards_path = root / ".agent/src/agent/core/implement/guards.py"
    gates_path = root / ".agent/src/agent/commands/runbook_gates.py"

    if guards_path.exists():
        content = guards_path.read_text(encoding="utf-8")
        # Remove the check_test_imports_resolvable function
        # This pattern matches from the function def until the next function def or end of file
        new_content = re.sub(
            r"\n\ndef check_test_imports_resolvable\(.*?\):\n(?:    .*\n?)*",
            "\n",
            content,
            flags=re.DOTALL
        )
        if new_content != content:
            guards_path.write_text(new_content, encoding="utf-8")
            logger.info("Successfully removed check_test_imports_resolvable from guards.py")

    if gates_path.exists():
        content = gates_path.read_text(encoding="utf-8")
        
        # 1. Remove from import list
        content = content.replace("check_test_imports_resolvable,\n    ", "")
        content = content.replace(", check_test_imports_resolvable", "")
        
        # 2. Remove _build_runbook_symbol_index helper
        content = re.sub(
            r"\n\ndef _build_runbook_symbol_index\(.*?\):\n(?:    .*\n?)*",
            "\n",
            content,
            flags=re.DOTALL
        )
        
        # 3. Remove Gate 3.7 orchestration block
        # Anchor: after gate35.corrections attribute
        content = re.sub(
            r"\s+# Gate 3\.7: Test Import Resolution.*?import_span\.set_attribute\(\"gate37\.corrections\", len\(correction_parts\)\)",
            "",
            content,
            flags=re.DOTALL
        )
        
        gates_path.write_text(content, encoding="utf-8")
        logger.info("Successfully reverted orchestration changes in runbook_gates.py")

if __name__ == "__main__":
    try:
        rollback()
        logger.info("Rollback of INFRA-178 complete.")
    except Exception as e:
        logger.error(f"Rollback failed: {e}")

