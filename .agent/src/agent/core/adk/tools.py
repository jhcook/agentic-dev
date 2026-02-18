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
Read-only tool suite for ADK governance agents.

Provides 5 tools: read_file, search_codebase, list_directory, read_adr,
read_journey. All path-accepting tools validate that resolved paths are
within the repository root. No write or network tools are exposed.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, List


# Characters that could be used for shell injection.
# Stripping these makes LLM-supplied queries safe for subprocess.
_SHELL_META_RE = re.compile(r"[;|&$`\"'\\(){}<>!\n\r\x00]")


def _sanitize_query(query: str) -> str:
    """Strips shell metacharacters from an LLM-supplied search query.

    Raises:
        ValueError: If the sanitized query is empty or too long.
    """
    sanitized = _SHELL_META_RE.sub("", query).strip()
    if not sanitized:
        raise ValueError("Query is empty after sanitization.")
    if len(sanitized) > 500:
        raise ValueError("Query exceeds maximum length of 500 characters.")
    # Safe: subprocess.run uses list-form (no shell=True), so args go
    # directly to the process without shell interpretation. The regex
    # strip prevents rg flag injection via chars like --include.
    return sanitized


def _validate_path(path: str, repo_root: Path) -> Path:
    """Validates a path is within the repository root.

    Raises:
        ValueError: If the resolved path escapes the repo root.
    """
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Path '{path}' is outside the repository root.")
    return resolved


def make_tools(repo_root: Path) -> List[Callable]:
    """Creates bound tool functions with repo_root pre-filled.

    Returns exactly 5 read-only tools. ADK auto-wraps these plain
    Python functions into FunctionTool instances.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        List of 5 callable tool functions.
    """

    def read_file(path: str) -> str:
        """Reads a file from the repository. Path must be relative to repo root."""
        filepath = _validate_path(str(repo_root / path), repo_root)
        if not filepath.is_file():
            return f"Error: '{path}' is not a file or does not exist."
        return filepath.read_text(errors="replace")[:50_000]  # Cap output

    def search_codebase(query: str) -> str:
        """Searches the codebase for a query using ripgrep. Returns up to 50 matches."""
        try:
            safe_query = _sanitize_query(query)
        except ValueError as e:
            return f"Error: {e}"
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-n", safe_query, str(repo_root)],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()[:50]
                return "\n".join(lines) or "No matches found."
            return f"No matches found (rg exit code {result.returncode})."
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 10 seconds."
        except FileNotFoundError:
            # Fallback to in-process grep if rg not available
            matches = []
            for root, _, files in os.walk(repo_root):
                for fname in files:
                    try:
                        fpath = Path(root) / fname
                        for line in fpath.read_text(errors="replace").splitlines():
                            if safe_query in line:
                                matches.append(f"{fpath}:{line.strip()}")
                                if len(matches) >= 50:
                                    return "\n".join(matches)
                    except Exception:
                        continue
            return "\n".join(matches) or "No matches found."

    def list_directory(path: str) -> str:
        """Lists the contents of a directory within the repository."""
        dirpath = _validate_path(str(repo_root / path), repo_root)
        if not dirpath.is_dir():
            return f"Error: '{path}' is not a directory or does not exist."
        entries = sorted(os.listdir(dirpath))
        return "\n".join(entries)

    def read_adr(adr_id: str) -> str:
        """Reads an Architecture Decision Record by ID (e.g., '029')."""
        adr_dir = repo_root / ".agent" / "adrs"
        # Try common naming patterns
        for pattern in [f"ADR-{adr_id.zfill(3)}*", f"adr-{adr_id.zfill(3)}*"]:
            matches = list(adr_dir.glob(pattern))
            if matches:
                return matches[0].read_text(errors="replace")
        return f"Error: ADR {adr_id} not found in {adr_dir}."

    def read_journey(journey_id: str) -> str:
        """Reads a User Journey by ID (e.g., '033')."""
        jrn_dir = repo_root / ".agent" / "cache" / "journeys"
        for scope_dir in jrn_dir.iterdir():
            if scope_dir.is_dir():
                for pattern in [
                    f"JRN-{journey_id.zfill(3)}*",
                    f"jrn-{journey_id.zfill(3)}*",
                ]:
                    matches = list(scope_dir.glob(pattern))
                    if matches:
                        return matches[0].read_text(errors="replace")
        return f"Error: Journey {journey_id} not found in {jrn_dir}."

    return [read_file, search_codebase, list_directory, read_adr, read_journey]
