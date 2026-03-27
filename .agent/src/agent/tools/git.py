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
Tools for performing Git operations within the repository.

Provides wrappers for diffing, history inspection, blaming, and basic
workspace management (commit, branch, stash).
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from agent.core.utils import scrub_sensitive_data

def _validate_path(path: str, repo_root: Path) -> Path:
    """Validates a path is within the repository root."""
    resolved = (repo_root / path).resolve()
    if not resolved.is_relative_to(repo_root.resolve()):
        raise ValueError(f"Path '{path}' is outside the repository root.")
    return resolved

def _run_git(args: List[str], repo_root: Path) -> str:
    """
    Executes a git command using subprocess.run.

    Args:
        args: List of command line arguments (excluding 'git').
        repo_root: The root of the git repository.

    Returns:
        The stdout of the command if successful.

    Raises:
        RuntimeError: If the git command fails.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        raise RuntimeError(f"Git error: {error_msg.strip()}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Git operation timed out after 30 seconds.")

def show_diff(path: Optional[str] = None, repo_root: Path = Path(".")) -> str:
    """
    Returns the unified diff of changes in the workspace.

    Args:
        path: Optional specific file path to diff.
        repo_root: Repository root path.
    """
    try:
        args = ["diff", "HEAD"]
        if path:
            args.append(str(_validate_path(path, repo_root)))
        return scrub_sensitive_data(_run_git(args, repo_root)) or "No changes detected."
    except Exception as e:
        return f"Error: {str(e)}"

def blame(path: str, repo_root: Path = Path(".")) -> str:
    """
    Provides line-by-line authorship information for a file.
    Returns a JSON-encoded list of objects.
    """
    try:
        filepath = _validate_path(path, repo_root)
        # Use short format for cleaner parsing: hash (author date line) content
        output = _run_git(["blame", "-s", str(filepath)], repo_root)
        
        parsed = []
        for line in output.splitlines():
            # Format: <hash> <line_num>) <content>
            match = re.match(r'^([a-f0-9^]+)\s+(\d+)\)\s*(.*)$', line)
            if match:
                parsed.append({
                    "commit": match.group(1),
                    "line": int(match.group(2)),
                    "content": match.group(3)
                })
        
        return json.dumps(parsed, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

def file_history(path: str, repo_root: Path = Path(".")) -> str:
    """
    Returns the commit history for a specific file.
    Returns a JSON-encoded list of commit summaries.
    """
    try:
        filepath = _validate_path(path, repo_root)
        # format: hash|author|date|subject
        log_format = "%H|%an|%ad|%s"
        output = _run_git([
            "log", 
            f"--pretty=format:{log_format}", 
            "--date=short", 
            "--max-count=20", 
            "--", 
            str(filepath)
        ], repo_root)
        
        history = []
        for line in output.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                history.append({
                    "commit": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "summary": parts[3]
                })
        
        return json.dumps(history, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

def stash(message: Optional[str] = None, repo_root: Path = Path(".")) -> str:
    """
    Stashes current changes in the workspace.
    """
    try:
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        return _run_git(args, repo_root) or "Changes stashed successfully."
    except Exception as e:
        return f"Error: {str(e)}"

def unstash(stash_id: Optional[int] = None, repo_root: Path = Path(".")) -> str:
    """
    Restores stashed changes.
    """
    try:
        args = ["stash", "pop"]
        if stash_id is not None:
            args.append(f"stash@{{{stash_id}}}")
        return _run_git(args, repo_root)
    except Exception as e:
        return f"Error: {str(e)}"

def commit(message: str, repo_root: Path = Path(".")) -> str:
    """
    Commits staged changes to the current branch.
    """
    try:
        if not message.strip():
            return "Error: Commit message cannot be empty."
        return _run_git(["commit", "-m", message], repo_root)
    except Exception as e:
        return f"Error: {str(e)}"

def create_branch(name: str, base: str = "HEAD", repo_root: Path = Path(".")) -> str:
    """
    Creates and switches to a new branch.
    """
    try:
        # Basic sanitization for branch names to prevent flag injection
        if name.startswith("-"):
            return "Error: Invalid branch name."
        
        return _run_git(["checkout", "-b", name, base], repo_root)
    except Exception as e:
        return f"Error: {str(e)}"
