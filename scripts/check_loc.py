#!/usr/bin/env python3

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
Copyright 2026 Justin Cook
License: Apache-2.0
Enforce 500 physical LOC ceiling on Python files.
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

WARN_LOC = 500
MAX_LOC = 1000
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def is_exempt(path: Path, content: str) -> bool:
    """Check if the given file path or content is exempt from LOC checking."""
    if "migrations/" in str(path):
        return True
    if "# nolint: loc-ceiling" in content:
        return True
    return False

def check_file(path: Path) -> Tuple[int, str]:
    """Check a specific file to see if it exceeds limits (ok, warn, fail)."""
    if path.stat().st_size > MAX_FILE_SIZE:
        return 0, "ok"
    try:
        content = path.read_text(encoding="utf-8")
        if is_exempt(path, content):
            return 0, "ok"
        lines = content.splitlines()
        count = len(lines)
        if count > MAX_LOC:
            return count, "fail"
        elif count > WARN_LOC:
            return count, "warn"
        return count, "ok"
    except (UnicodeDecodeError, PermissionError):
        return 0, "ok"

def main():
    """Main function to iterate through files and report violations/warnings."""
    root = Path(".agent/src/agent")
    if not root.exists():
        root = Path("src/agent")
    
    violations = []
    warnings = []
    for p in root.rglob("*.py"):
        if p.is_symlink(): continue
        count, status = check_file(p)
        if status == "fail":
            violations.append({"file": str(p), "loc": count})
        elif status == "warn":
            warnings.append({"file": str(p), "loc": count})

    if "--format" in sys.argv and "json" in sys.argv:
        print(json.dumps({"violations": violations, "warnings": warnings}))
    else:
        for w in warnings:
            print(f"WARN: {w['file']} exceeds 500 LOC ({w['loc']}). Consider resolving (Industry Goldilocks Zone: 100-300 lines).")
        for v in violations:
            print(f"FAIL: {v['file']} exceeds 1000 LOC hard limit ({v['loc']}). Fix: agent preflight --gate quality")
    
    sys.exit(1 if violations else 0)

if __name__ == "__main__":
    main()
