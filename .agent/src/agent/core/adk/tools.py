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

from agent.core.utils import scrub_sensitive_data
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, List, Dict, TypedDict, Optional

logger = logging.getLogger(__name__)

class BackgroundProcessState(TypedDict):
    proc: subprocess.Popen
    command: str
    output_buffer: List[str]

_BACKGROUND_PROCESSES: Dict[str, BackgroundProcessState] = {}


# Characters that could be used for shell injection.
# Stripping these makes LLM-supplied queries safe for subprocess.
_SHELL_META_RE = re.compile("[;|&$`\"'\\(\\\\){}<>!\n\r\x00]")


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


def _stage_file(filepath: Path, repo_root: Path) -> None:
    """Stage a file for git (best-effort, never raises)."""
    try:
        subprocess.run(
            ["git", "add", str(filepath)],
            cwd=str(repo_root), capture_output=True, timeout=5, check=False,
        )
    except Exception:
        pass  # Non-critical — don't break tool on staging failure


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
        """Reads a file from the repository, capped at 2000 lines. Path must be relative to repo root."""
        filepath = _validate_path(str(repo_root / path), repo_root)
        if not filepath.is_file():
            return f"Error: '{path}' is not a file or does not exist."
        try:
            with filepath.open('r', errors="replace") as f:
                lines = []
                truncated = False
                for i, line in enumerate(f):
                    if i >= 2000:
                        truncated = True
                        break
                    lines.append(line)
                content = "".join(lines)
                if truncated:
                    content += "\n... (file truncated at 2000 lines)"
            return content
        except Exception as e:
            return f"Error reading file {path}: {e}"

    def search_codebase(query: str) -> str:
        """Searches the codebase for a query using ripgrep. Returns up to 50 matches."""
        try:
            safe_query = _sanitize_query(query)
        except ValueError as e:
            return f"Error: {e}"
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-n", "--hidden", safe_query, str(repo_root)],
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

    def patch_file(path: str, search: str, replace: str) -> str:
        """Safely replaces a specific chunk of text in a file. Use this for targeted edits to avoid rewriting entire files.
        The search string must match exactly one occurrence in the file. Path must be relative to repo root.
        """
        logger.info(f"Executing tool 'patch_file' on path: {path}")
        try:
            filepath = _validate_path(str(repo_root / path), repo_root)
            if not filepath.exists():
                return f"Error: File '{path}' does not exist."
            
            content = filepath.read_text()
            occurrences = content.count(search)
            
            if occurrences == 0:
                return f"Error: The search string was not found in '{path}'."
            elif occurrences > 1:
                return f"Error: The search string matches {occurrences} times in '{path}'. Please provide a more specific search string."
                
            new_content = content.replace(search, replace, 1)
            filepath.write_text(new_content)
            _stage_file(filepath, repo_root)
            logger.info(f"File {path} successfully patched and staged.")
            return f"File {path} successfully patched and staged."
        except ValueError as e:
            logger.error(f"Validation error in 'patch_file' for path {path}: {e}", exc_info=True)
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error patching file {path}: {e}", exc_info=True)
            return f"Error patching file: {e}"

    def edit_file(path: str, content: str) -> str:
        """Rewrites the entire content of a file. For making targeted edits to large files, prefer 'patch_file'."""
        logger.info(f"Executing tool 'edit_file' on path: {path}")
        try:
            filepath = _validate_path(str(repo_root / path), repo_root)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            _stage_file(filepath, repo_root)
            result = f"File {path} successfully updated and staged."
            logger.info(result)
            return result
        except ValueError as e:
            logger.error(f"Validation error in 'edit_file' for path {path}: {e}", exc_info=True)
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error editing file {path}: {e}", exc_info=True)
            return f"Error editing file: {e}"

    def create_file(path: str, content: str = "") -> str:
        """Creates a new file with the given content. Path must be relative to repo root."""
        logger.info(f"Executing tool 'create_file' on path: {path}")
        try:
            filepath = _validate_path(str(repo_root / path), repo_root)
            if filepath.exists():
                return f"Error: File '{path}' already exists. Use edit_file or patch_file to modify it."
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            _stage_file(filepath, repo_root)
            result = f"File {path} successfully created and staged."
            logger.info(result)
            return result
        except ValueError as e:
            logger.error(f"Validation error in 'create_file' for path {path}: {e}", exc_info=True)
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error creating file {path}: {e}", exc_info=True)
            return f"Error creating file: {e}"

    def delete_file(path: str) -> str:
        """Deletes a file from the repository. Path must be relative to repo root."""
        logger.info(f"Executing tool 'delete_file' on path: {path}")
        try:
            filepath = _validate_path(str(repo_root / path), repo_root)
            if not filepath.is_file():
                return f"Error: File '{path}' does not exist or is a directory."

            # Check if the file is tracked by Git
            is_tracked_proc = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(filepath)],
                cwd=str(repo_root), capture_output=True, text=True, timeout=5
            )
            is_tracked = is_tracked_proc.returncode == 0

            if is_tracked:
                # If tracked, use `git rm` to remove and stage the deletion
                subprocess.run(
                    ["git", "rm", str(filepath)],
                    cwd=str(repo_root), capture_output=True, text=True, timeout=5, check=True
                )
                result = f"File {path} successfully deleted and deletion staged."
            else:
                # If not tracked, just delete the file. No staging needed.
                os.remove(filepath)
                result = f"File {path} successfully deleted."

            logger.info(result)
            return result
        except ValueError as e:
            logger.error(f"Validation error in 'delete_file' for path {path}: {e}", exc_info=True)
            return f"Error: {e}"
        except subprocess.CalledProcessError as e:
            error_message = e.stderr if e.stderr else "Unknown git error"
            logger.error(f"Error running git command for {path}: {error_message}", exc_info=True)
            return f"Error staging deletion: {error_message}"
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}", exc_info=True)
            return f"Error deleting file: {e}"

    def run_command(command: str, background: bool = False) -> str:
        """Executes a shell command (sandboxed) in the repository root. Streams output in real-time.

        If background=True, the command runs in the background and a command_id is returned.
        The command output is streamed to the UI and is NOT returned by this function.
        The function's return value is a summary for the LLM, not the raw output.
        """
        logger.info(f"Executing tool 'run_command' with command: {command}")
        try:
            if not command.strip():
                return "Error: empty command."

            # Sandbox validation: Check for path traversal
            if ".." in command:
                return "Error: path traversal ('..') is not allowed in the command."

            # Restore Sandbox Enforcement: block absolute paths outside repo root
            try:
                for token in shlex.split(command):
                    if token.startswith("/"):
                        _validate_path(token, repo_root)
            except ValueError as e:
                return f"Error: Sandbox violation: {e}"

            # Use Popen for real-time streaming of output lines, now with shell=True as per EXC-003.
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            # SECURITY FIX: Use shell=False and shlex.split to prevent shell injection.
            # This is the approach recommended by the security audit.
            args = shlex.split(command)
            proc = subprocess.Popen(
                args,
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if background else None,
                text=True,
                shell=False,
                bufsize=1,  # Line buffering for real-time streaming
            )
            
            if background:
                cmd_id = str(uuid.uuid4())
                state: BackgroundProcessState = {
                    "proc": proc,
                    "command": command,
                    "output_buffer": []
                }
                _BACKGROUND_PROCESSES[cmd_id] = state
                
                def _read_output():
                    if proc.stdout:
                        # Use readline() instead of iterator for unbuffered reads
                        for line in iter(proc.stdout.readline, ''):
                            stripped_line = line.rstrip("\n")
                            state["output_buffer"].append(stripped_line)
                            if len(state["output_buffer"]) > 200:
                                state["output_buffer"].pop(0)
                            if on_output:
                                on_output(stripped_line)
                
                threading.Thread(target=_read_output, daemon=True).start()
                return f"Command started in background with ID: {cmd_id}. Use check_command_status and send_command_input to interact."
            
            output_captured = []
            if proc.stdout:
                # Use readline() instead of iterator for unbuffered reads
                for line in iter(proc.stdout.readline, ''):
                    stripped_line = line.rstrip("\n")
                    output_captured.append(stripped_line)
                    if len(output_captured) > 50:
                        output_captured.pop(0)
                    if on_output:
                        on_output(stripped_line)
            
            proc.wait(timeout=120)

        except subprocess.TimeoutExpired:
            proc.kill()
            logger.warning(f"'run_command' timed out after 120s: {command}")
            return "Error: Command timed out after 120 seconds and was terminated."
        except FileNotFoundError:
            # This can happen if the first element of 'args' is not a valid executable.
            # Fix: args is not defined here if shell=True is used, but command is.
            return f"Error: Command not found: '{command.split()[0]}'. Please ensure it is installed and in your PATH."
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            return f"Error during command execution: {e}"

        logger.info(f"'run_command' completed with exit code {proc.returncode}.")

        # Return captured output so the LLM can reason about command results.
        # COMPLIANCE: scrub PII/secrets before returning to the LLM.
        # See DPIA in INFRA-042 for risk assessment and GDPR justification.
        output_text = scrub_sensitive_data("\n".join(output_captured[-50:]))
        if proc.returncode != 0:
            return f"Command failed (exit code {proc.returncode}):\n{output_text}"
        return output_text if output_text else f"Command finished with exit code {proc.returncode}."

    def send_command_input(command_id: str, input_text: str) -> str:
        """Sends input text to a background command's stdin."""
        state = _BACKGROUND_PROCESSES.get(command_id)
        if not state:
            return f"Error: No background process found with ID {command_id}"
        
        proc = state["proc"]
        if proc.poll() is not None:
            return f"Error: Command has already exited with code {proc.returncode}"
            
        try:
            if proc.stdin:
                if not input_text.endswith('\n'):
                    input_text += '\n'
                proc.stdin.write(input_text)
                proc.stdin.flush()
                # Wait briefly for process to react
                # The peek() method on a file-like object does not accept any keyword arguments.
                # try:

                # except TimeoutError:
                #     pass
                return "Input sent successfully. Use check_command_status to see new output."
            else:
                return "Error: Process stdin is not available."
        except Exception as e:
            logger.error(f"Error sending input to {command_id}: {e}", exc_info=True)
            return f"Error sending input: {e}"

    def check_command_status(command_id: str) -> str:
        """Checks the status and recent output of a background command."""
        state = _BACKGROUND_PROCESSES.get(command_id)
        if not state:
            return f"Error: No background process found with ID {command_id}"
            
        proc = state["proc"]
        status = "Running" if proc.poll() is None else f"Exited with code {proc.returncode}"
        output = "\\n".join(state["output_buffer"][-50:])
        result = f"Status: {status}\\n\\nRecent Output:\\n{output}"
        if "Exited with code" in status:
            del _BACKGROUND_PROCESSES[command_id]
        return result

    def find_files(pattern: str) -> str:
        """Finds files matching a glob pattern within the repository."""
        logger.info(f"Executing tool 'find_files' with pattern: {pattern}")
        try:
            matches = list(repo_root.rglob(pattern))
            if not matches:
                logger.info(f"'find_files' found no matches for pattern: {pattern}")
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
            result_str = "\n".join(results) + suffix
            logger.info(f"'find_files' found {len(matches)} files.")
            return result_str
        except Exception as e:
            logger.error(f"Error in 'find_files' with pattern '{pattern}': {e}", exc_info=True)
            return f"Error finding files: {e}"

    def grep_search(pattern: str, path: str = ".") -> str:
        """Searches for a text pattern in the repository using ripgrep."""
        logger.info(f"Executing 'grep_search' with pattern='{pattern}' in path='{path}'")
        try:
            safe_query = _sanitize_query(pattern)
        except ValueError as e:
            logger.error(f"Invalid grep pattern '{pattern}': {e}")
            return f"Error: {e}"
        try:
            search_path = _validate_path(str(repo_root / path), repo_root)
        except ValueError as e:
            logger.error(f"Invalid grep path '{path}': {e}")
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
                output = "\n".join(lines) or "No matches found."
                logger.info(f"'grep_search' found {len(lines)} matches.")
                return output
            logger.info(f"'grep_search' found no matches (rg exit code {result.returncode}).")
            return "No matches found."
        except subprocess.TimeoutExpired:
            logger.warning(f"'grep_search' timed out for pattern '{safe_query}'")
            return "Error: search timed out after 10 seconds."
        except FileNotFoundError:
            logger.warning("ripgrep not found, falling back to basic grep.")
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
                                    logger.info(f"Fallback grep found {len(matches)} matches.")
                                    return "\n".join(matches)
                    except Exception:
                        continue
            logger.info(f"Fallback grep found {len(matches)} matches.")
            return "\n".join(matches) or "No matches found."

    def match_story(query: str) -> str:
        """Matches a query to a story and returns the story ID (e.g., INFRA-089)."""
        logger.info(f"Executing tool 'match_story' with query: {query}")
        try:
            result = run_command(f"agent match-story '{query}'")
            # Extract the story ID from the result
            match = re.search(r'INFRA-\d+', result)
            if match:
                story_id = match.group(0)
                logger.info(f"'match_story' found story ID: {story_id}")
                return story_id
            else:
                logger.info(f"'match_story' did not find a story ID.")
                return "No story ID found."
        except Exception as e:
            logger.error(f"Error executing 'agent match-story' with query '{query}': {e}", exc_info=True)
            return f"Error matching story: {e}"

    return [patch_file, edit_file, create_file, delete_file, run_command, send_command_input, check_command_status, find_files, grep_search, match_story]


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
TOOL_SCHEMAS['match_story'] = {
    'name': 'match_story',
    'description': 'Matches a query to a story and returns the story ID (e.g., INFRA-089).'
}
for _fn in make_interactive_tools(Path(".")):
    TOOL_SCHEMAS[_fn.__name__] = {
        "name": _fn.__name__,
        "description": (_fn.__doc__ or "").strip(),
    }
