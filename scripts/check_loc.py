#!/usr/bin/env python3
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

MAX_LOC = 500
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def is_exempt(path: Path, content: str) -> bool:
    """Check if the given file path or content is exempt from LOC checking."""
    if "migrations/" in str(path):
        return True
    if "# nolint: loc-ceiling" in content:
        return True
    return False

def check_file(path: Path) -> Tuple[int, bool]:
    """Check a specific file to see if it exceeds the LOC limit."""
    if path.stat().st_size > MAX_FILE_SIZE:
        return 0, False
    try:
        content = path.read_text(encoding="utf-8")
        if is_exempt(path, content):
            return 0, True
        lines = content.splitlines()
        return len(lines), len(lines) <= MAX_LOC
    except (UnicodeDecodeError, PermissionError):
        return 0, True

def main():
    """Main function to iterate through files and report violations."""
    root = Path(".agent/src/agent")
    if not root.exists():
        root = Path("src/agent")
    
    violations = []
    for p in root.rglob("*.py"):
        if p.is_symlink(): continue
        count, ok = check_file(p)
        if not ok:
            violations.append({"file": str(p), "loc": count})

    if "--format" in sys.argv and "json" in sys.argv:
        print(json.dumps(violations))
    else:
        for v in violations:
            print(f"FAIL: {v['file']} exceeds 500 LOC ({v['loc']}). Fix: agent preflight --gate quality")
    
    sys.exit(1 if violations else 0)

if __name__ == "__main__":
    main()
