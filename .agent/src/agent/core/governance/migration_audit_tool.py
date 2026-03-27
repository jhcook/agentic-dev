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

"""Utility to verify that migrated test files are sanitized of local PII and credentials."""

import re
import os
from pathlib import Path
from typing import List, Tuple

# Common patterns for leaked local data or credentials
AUDIT_PATTERNS = {
    "OpenAI Key": r"sk-[a-zA-Z0-9]{48}",
    "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Anthropic Key": r"sk-ant-api03-[a-zA-Z0-9-_]{93}",
    "Local Home Path (Unix)": r"/Users/[a-zA-Z0-9._-]+",
    "Local Home Path (Windows)": r"[a-zA-Z]:\\Users\\[a-zA-Z0-9._-]+",
    "Generic Password Variable": r'(?i)password\s*=\s*["\'][^"\']{4,}["\']'
}

def run_security_audit(target_dir: str = ".agent/tests") -> List[Tuple[str, str, str]]:
    """
    Scans all files in target_dir for sensitive patterns.
    
    Returns:
        List of (file_path, pattern_name, match_text)
    """
    findings = []
    root = Path(target_dir)
    
    if not root.exists():
        return []

    for py_file in root.rglob("*.py"):
        content = py_file.read_text()
        for name, pattern in AUDIT_PATTERNS.items():
            matches = re.findall(pattern, content)
            for match in matches:
                findings.append((str(py_file), name, match))
                
    return findings

if __name__ == "__main__":
    print("Starting Security Audit of migrated tests...")
    results = run_security_audit()
    if not results:
        print("✅ No sensitive data or local paths detected in migrated files.")
    else:
        print(f"❌ Found {len(results)} potential security violations:")
        for file, ptype, match in results:
            print(f"  - {file}: {ptype} detected")
        exit(1)
