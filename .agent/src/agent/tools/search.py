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
Tools for searching and navigating the codebase.

Provides Ripgrep-powered text search, directory listing, and AST-aware
symbol lookup for Python files.
"""

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from agent.core.utils import scrub_sensitive_data

# Characters that could be used for shell injection.
_SHELL_META_RE = re.compile("[;|&$`\"'\\(\\\\){}<>!\n\r\x00]")

def _sanitize_query(query: str) -> str:
    """Strips shell metacharacters from a search query."""
    sanitized = _SHELL_META_RE.sub("", query).strip()
    if not sanitized:
        raise ValueError("Query is empty after sanitization.")
    if len(sanitized) > 500:
        raise ValueError("Query exceeds maximum length of 500 characters.")
    return sanitized

def _validate_path(path: str, repo_root: Path) -> Path:
    """Validates a path is within the repository root."""
    resolved = (repo_root / path).resolve()
    if not resolved.is_relative_to(repo_root.resolve()):
        raise ValueError(f"Path '{path}' is outside the repository root.")
    return resolved

def search_codebase(query: str, repo_root: Path) -> str:
    """
    Searches the entire codebase for a query using ripgrep.
    Returns up to 50 matches.
    """
    try:
        safe_query = _sanitize_query(query)
        result = subprocess.run(
            ["rg", "--no-heading", "-n", "--hidden", "-e", safe_query, str(repo_root)],
            capture_output=True, text=True, timeout=15, check=False
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()[:50]
            output = "\n".join(lines) or "No matches found."
            return scrub_sensitive_data(output)
        return "No matches found."
    except subprocess.TimeoutExpired:
        return "Error: Search timed out after 15 seconds."
    except Exception as e:
        return f"Error during search: {str(e)}"

def grep_search(pattern: str, path: str = ".", repo_root: Path = Path(".")) -> str:
    """
    Searches for a text pattern in a specific path using ripgrep.
    """
    try:
        safe_pattern = _sanitize_query(pattern)
        search_path = _validate_path(path, repo_root)
        result = subprocess.run(
            ["rg", "--no-heading", "-n", "-e", safe_pattern, str(search_path)],
            capture_output=True, text=True, timeout=10, check=False
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()[:50]
            return scrub_sensitive_data("\n".join(lines) or "No matches found.")
        return "No matches found."
    except Exception as e:
        return f"Error: {str(e)}"

def list_directory(path: str, repo_root: Path) -> str:
    """
    Lists the contents of a directory within the repository.
    """
    try:
        dirpath = _validate_path(path, repo_root)
        if not dirpath.is_dir():
            return f"Error: '{path}' is not a directory or does not exist."
        entries = sorted(os.listdir(dirpath))
        return "\n".join(entries)
    except Exception as e:
        return f"Error: {str(e)}"

def find_symbol(symbol_name: str, repo_root: Path) -> str:
    """
    Locates a function or class definition by name using AST parsing.
    Only supports Python files.
    """
    try:
        # Optimization: Use ripgrep to find candidate files first (lazy loading)
        candidate_files = subprocess.run(
            ["rg", "-l", f"\\b(class|def)\\s+{symbol_name}\\b", "--glob", "*.py", str(repo_root)],
            capture_output=True, text=True, check=False
        ).stdout.splitlines()

        results = []
        for file_path_str in candidate_files:
            file_path = Path(file_path_str)
            if file_path.suffix != ".py":
                continue

            try:
                content = file_path.read_text(errors="replace")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name == symbol_name:
                            rel_path = file_path.relative_to(repo_root)
                            symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"
                            results.append(f"{rel_path}:{node.lineno} ({symbol_type} definition)")
            except SyntaxError:
                continue  # Skip malformed files

        if not results:
            return f"Symbol '{symbol_name}' not found in Python files."
        return "\n".join(results)

    except Exception as e:
        return f"Error during symbol lookup: {str(e)}"

def find_references(symbol_name: str, repo_root: Path) -> str:
    """
    Finds all references to a symbol name across the codebase using ripgrep.
    """
    try:
        # Search for the symbol as a whole word
        safe_symbol = _sanitize_query(symbol_name)
        result = subprocess.run(
            ["rg", "--no-heading", "-n", "--hidden", "-w", "-e", safe_symbol, str(repo_root)],
            capture_output=True, text=True, timeout=15, check=False
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()[:50]
            return scrub_sensitive_data("\n".join(lines) or "No references found.")
        return "No references found."
    except Exception as e:
        return f"Error finding references: {str(e)}"
