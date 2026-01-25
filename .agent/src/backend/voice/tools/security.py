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

from langchain_core.tools import tool
import re

@tool
def scan_secrets_in_content(content: str) -> str:
    """
    Scan text content for potential secrets (API keys, tokens).
    Returns proper findings without revealing the secret itself.
    """
    # Simple regex patterns for demo
    patterns = {
        "API Key": r"(?i)(api[_-]?key|sk-[a-zA-Z0-9]{20,})",
        "Token": r"(?i)token",
        "Secret": r"(?i)secret"
    }
    findings = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines):
        for name, pattern in patterns.items():
            if re.search(pattern, line):
                findings.append(f"Potential {name} found at line {line_idx+1}")
                
    if not findings:
        return "No obvious secrets found."
    return "\n".join(findings)
