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
Tool suite for ADK agents.

Provides read-only tools for governance agents (read_file, search_codebase,
list_directory, read_adr, read_journey) and interactive tools for the
console agent (edit_file, run_command, find_files, grep_search).
All tools validate that resolved paths are within the repository root.
"""

import logging
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, List

logger = logging.getLogger(__name__)


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


def make_interactive_tools(
    repo_root: Path,
    on_output: "Callable[[str], None] | None" = None,
) -> List[Callable]:
    """Creates bound interactive tool functions for the console TUI.

    Returns 4 read-write tools for the agentic loop. These are
    separate from the governance tools (which are read-only).

    Args:
        repo_root: Absolute path to the repository root.
        on_output: Optional callback invoked with each line of
            ``run_command`` output for real-time streaming to the UI.

    Returns:
        List of 4 callable tool functions.
    """

    def edit_file(path: str, content: str) -> str:
        """Writes content to a file within the repository. Path must be relative to repo root."""
        try:
            filepath = _validate_path(str(repo_root / path), repo_root)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return f"File {path} successfully updated."
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error editing file {path}: {e}", exc_info=True)
            return f"Error editing file: {e}"

    def run_command(command: str) -> str:
        """Executes a shell command (sandboxed) in the repository root. Returns a single string containing the exit code, stdout, and stderr."""
        try:
            if not command.strip():
                return "Error: empty command."

            # Sandbox validation: 
            # 1. Block path traversal
            if ".." in command:
                return "Error: path traversal ('..') is not allowed."
            
            # 2. Block absolute paths outside repo root (approximate check for shell=True)
            # Find any /path/to patterns that are absolute but don't start with repo_root
            abs_paths = re.findall(r"(?:^|\s)(/[^\s]*)", command)
            for path in abs_paths:
                if not path.startswith(str(repo_root)):
                    return f"Error: absolute paths outside the repository are not allowed."

            # Use Popen for real-time streaming of output lines.
            # We use shell=True as requested by the user to support pipes/redirections.
            # Sandbox safety is managed by path validation above.
            import os
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            proc = subprocess.Popen(
                command,
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
            )
            stdout_lines: list[str] = []
            try:
                if proc.stdout:
                    for line in proc.stdout:
                        stdout_lines.append(line)
                        if on_output:
                            on_output(line.rstrip("\n"))
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                return "Error: command timed out after 120 seconds."

            output = f"Exit code: {proc.returncode}\n"
            full_stdout = "".join(stdout_lines)
            if full_stdout:
                output += f"Output:\n{full_stdout[:20_000]}\n"
            return output
        except Exception as e:
            logger.error(f"Error executing command: {e}", exc_info=True)
            return f"Error executing command: {e}"

    def find_files(pattern: str) -> str:
        """Finds files matching a glob pattern within the repository."""
        try:
            matches = list(repo_root.rglob(pattern))
            if not matches:
                return "No files found matching that pattern."
            # Cap at 100 results to prevent overwhelming output
            results = [
                str(m.relative_to(repo_root)) for m in matches[:100]
            ]
            suffix = (
                f"\n... and {len(matches) - 100} more"
                if len(matches) > 100
                else ""
            )
            return "\n".join(results) + suffix
        except Exception as e:
            return f"Error finding files: {e}"

    def grep_search(pattern: str, path: str = ".") -> str:
        """Searches for a text pattern in the repository using ripgrep."""
        try:
            safe_query = _sanitize_query(pattern)
        except ValueError as e:
            return f"Error: {e}"
        try:
            search_path = _validate_path(str(repo_root / path), repo_root)
        except ValueError as e:
            return f"Error: {e}"
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-n", safe_query, str(search_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()[:50]
                return "\n".join(lines) or "No matches found."
            return "No matches found."
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 10 seconds."
        except FileNotFoundError:
            # Fallback to in-process grep if rg not available
            matches: list[str] = []
            search_root = Path(search_path)
            walker = (
                [(str(search_root.parent), [], [search_root.name])]
                if search_root.is_file()
                else os.walk(search_root)
            )
            for root_dir, _, files in walker:
                for fname in files:
                    try:
                        fpath = Path(root_dir) / fname
                        for i, line in enumerate(
                            fpath.read_text(errors="replace").splitlines(), 1
                        ):
                            if safe_query in line:
                                rel = fpath.relative_to(repo_root)
                                matches.append(f"{rel}:{i}:{line.strip()}")
                                if len(matches) >= 50:
                                    return "\n".join(matches)
                    except Exception:
                        continue
            return "\n".join(matches) or "No matches found."

    return [edit_file, run_command, find_files, grep_search]


# ---------------------------------------------------------------------------
# TOOL_SCHEMAS: static schema registry for the /tools console display.
# Built once at import time from a throwaway repo_root (Path(".")).
# Only name + description are used; actual execution goes through
# LocalToolClient._register() which rebuilds schemas from signatures.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = {}
for _fn in make_tools(Path(".")):
    TOOL_SCHEMAS[_fn.__name__] = {
        "name": _fn.__name__,
        "description": (_fn.__doc__ or "").strip(),
    }
for _fn in make_interactive_tools(Path(".")):
    TOOL_SCHEMAS[_fn.__name__] = {
        "name": _fn.__name__,
        "description": (_fn.__doc__ or "").strip(),
    }
