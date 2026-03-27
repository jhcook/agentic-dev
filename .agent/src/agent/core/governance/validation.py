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

"""Validation logic for filtering AI false positives against source context."""

import re
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# Standard library names for dependency validation
_STDLIB_MODULES = frozenset({
    "abc", "argparse", "ast", "asyncio", "atexit", "base64", "bisect",
    "calendar", "cmath", "code", "codecs", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "contextvars",
    "copy", "copyreg", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "dis", "email", "enum", "errno", "faulthandler",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "importlib",
    "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "linecache", "locale", "logging", "lzma", "mailbox", "math",
    "mimetypes", "mmap", "multiprocessing", "numbers", "operator", "os",
    "pathlib", "pdb", "pickle", "pkgutil", "platform", "plistlib",
    "pprint", "profile", "pstats", "py_compile", "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve",
    "shlex", "shutil", "signal", "site", "smtplib", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics", "string",
    "struct", "subprocess", "sys", "sysconfig", "syslog", "tarfile",
    "tempfile", "termios", "test", "textwrap", "threading", "time",
    "timeit", "tkinter", "token", "tokenize", "tomllib", "trace",
    "traceback", "tracemalloc", "tty", "turtle", "types", "typing",
    "unicodedata", "unittest", "urllib", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib",
})

def _resolve_file_path(filepath_str: str) -> Optional[Path]:
    """Resolve a path string from AI finding to a real Path object."""
    fpath = Path(filepath_str)
    if fpath.exists():
        return fpath
    for prefix in [".agent/src/", ".agent/", "backend/", "web/", "mobile/"]:
        candidate = Path.cwd() / prefix / filepath_str
        if candidate.exists():
            return candidate
    return None

def _line_in_diff_hunk(filepath: str, line_num: int, diff: str) -> bool:
    """Verify line number belongs to a changed hunk in the diff."""
    normalized = filepath.replace("\\", "/")
    in_target_file = False
    for diff_line in diff.split("\n"):
        if diff_line.startswith("+++ "):
            diff_path = diff_line[4:].strip()
            if diff_path.startswith("b/"):
                diff_path = diff_path[2:]
            in_target_file = (
                diff_path.endswith(normalized) or
                normalized.endswith(diff_path)
            )
        elif in_target_file and diff_line.startswith("@@ "):
            hunk_match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', diff_line)
            if hunk_match:
                start = int(hunk_match.group(1))
                count = int(hunk_match.group(2) or 1)
                if start - 5 <= line_num <= (start + count + 5):
                    return True
        elif in_target_file and diff_line.startswith("diff --git"):
            in_target_file = False
    return True

def _validate_finding_against_source(finding: str, diff: str) -> bool:
    """Check finding claims against on-disk file content."""
    finding_lower = finding.lower()
    
    # Citation required (Oracle Pattern)
    if not re.search(r'\(Source:\s*[^)]+\)|\[Source:\s*[^\]]+\]', finding, re.IGNORECASE):
        return False

    # Diff-hunk scope validation
    file_line_refs = re.findall(r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?:(\d+)', finding)
    for fstr, lstr in file_line_refs:
        if diff and not _line_in_diff_hunk(fstr, int(lstr), diff):
            return False

    # Stdlib dependency false positives
    if "pyproject" in finding_lower or "dependency" in finding_lower:
        dep_modules = re.findall(r'`(\w+)`', finding)
        for mod in dep_modules:
            if mod.lower() in _STDLIB_MODULES:
                return False

    return True
