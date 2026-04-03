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

"""Rollback utility for INFRA-176 syntax gate."""
import re
import sys
from pathlib import Path

def rollback_infra_176() -> None:
    """Removes the Gate 3.5 OTel span block from the runbook_gates pipeline."""
    gates_path = Path(".agent/src/agent/commands/runbook_gates.py")

    if not gates_path.exists():
        print(f"Error: {gates_path} not found.")
        sys.exit(1)

    content = gates_path.read_text(encoding="utf-8")

    # Match from the Gate 3.5 comment through the closing syn_span attribute,
    # inclusive — the entire `with tracer.start_as_current_span(...)` block.
    pattern = (
        r"\n    # Gate 3\.5: Projected Syntax Validation.*?"
        r'syn_span\.set_attribute\("gate35\.corrections"[^\n]*\)\n'
    )

    if not re.search(pattern, content, re.DOTALL):
        print("INFRA-176 gate block not found — no action needed.")
        return

    new_content = re.sub(pattern, "\n", content, flags=re.DOTALL)
    gates_path.write_text(new_content, encoding="utf-8")
    print("Successfully rolled back INFRA-176: Projected syntax gate removed.")

if __name__ == "__main__":
    rollback_infra_176()
