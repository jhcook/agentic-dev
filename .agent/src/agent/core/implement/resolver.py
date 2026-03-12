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

"""Resolver utilities for repository path search and story ID extraction."""

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.console import Console

_console = Console()

COMMON_FILES = {"__init__.py", "main.py", "config.py", "utils.py", "conftest.py"}
TRUSTED_ROOT_PREFIXES = (".agent/", "agent/", "backend/", "web/", "mobile/")


def _find_file_in_repo(filename: str) -> List[str]:
    """Return tracked git paths whose basename matches filename.

    Args:
        filename: Basename to search for.

    Returns:
        List of repo-relative paths matching the basename.
    """
    try:
        result = subprocess.check_output(
            ["git", "ls-files", "*" + filename], stderr=subprocess.DEVNULL
        ).decode().strip()
        return result.split("\n") if result else []
    except Exception:
        return []


def _find_directories_in_repo(dirname: str) -> List[str]:
    """Search for directories with a specific name in the repo.

    Excludes .git, node_modules, and dist to prevent false positives.

    Args:
        dirname: Directory basename to search for.

    Returns:
        List of repo-relative directory paths.
    """
    try:
        cmd = [
            "find", ".",
            "-path", "./.git", "-prune",
            "-o", "-path", "*/node_modules", "-prune",
            "-o", "-path", "*/dist", "-prune",
            "-o", "-type", "d", "-name", dirname, "-print",
        ]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return [p.lstrip("./") for p in result.split("\n") if p] if result else []
    except Exception:
        return []


def extract_story_id(content: str) -> Optional[str]:
    """Extract the first story ID (e.g. INFRA-042) from content.

    Args:
        content: Text to search, typically a runbook or story file.

    Returns:
        First matching story ID string, or None if not found.
    """
    match = re.search(r"\b([A-Z]+-\d+)\b", content)
    return match.group(1) if match else None


def resolve_path(filepath: str) -> Optional[Path]:
    """Resolve a file path to a real location, with fuzzy fallback.

    Resolution order:

    1. Exact match — return as-is.
    2. Single unique file match in repo — auto-redirect.
    3. New file with trusted root prefix — trust the full path.
    4. New file with unknown prefix — fuzzy-search directory by directory.

    Args:
        filepath: Repo-relative file path (may be AI-generated).

    Returns:
        Resolved :class:`pathlib.Path`, or ``None`` if ambiguous/invalid.
    """
    file_path = Path(filepath)
    if file_path.exists():
        return file_path

    # Trusted paths know exactly where they want to live — skip fuzzy search.
    is_trusted = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)
    if is_trusted:
        return file_path

    if file_path.name not in COMMON_FILES:
        candidates = _find_file_in_repo(file_path.name)
        exact = [c for c in candidates if Path(c).name == file_path.name]
        if len(exact) == 1:
            new_path = exact[0]
            if new_path != filepath:
                _console.print(f"[yellow]⚠️  Path Auto-Correct (File): '{filepath}' -> '{new_path}'[/yellow]")
                logging.warning(
                    "Path auto-corrected via fuzzy match",
                    extra={
                        "event": "path_auto_correction",
                        "original_path": filepath,
                        "resolved_path": new_path
                    }
                )
            return Path(new_path)
        if len(exact) > 1:
            _console.print(f"[bold red]❌ Ambiguous file path '{filepath}'. Found {len(exact)} matches.[/bold red]")
            return None

    parts = file_path.parts
    current_check = Path(".")

    for i, part in enumerate(parts[:-1]):
        next_check = current_check / part
        if not next_check.exists():
            _console.print(f"[dim]Directory '{next_check}' not found; searching for '{part}'...[/dim]")
            dir_candidates = _find_directories_in_repo(str(part))
            if len(dir_candidates) == 0:
                _console.print(f"[bold red]❌ Cannot resolve directory '{part}'.[/bold red]")
                return None
            if len(dir_candidates) == 1:
                rest = Path(*parts[i + 1:])
                new_full = Path(dir_candidates[0]) / rest
                _console.print(f"[yellow]⚠️  Path Auto-Correct (Dir): '{filepath}' -> '{new_full}'[/yellow]")
                logging.warning(
                    "Path auto-corrected via fuzzy match",
                    extra={
                        "event": "path_auto_correction",
                        "original_path": filepath,
                        "resolved_path": str(new_full)
                    }
                )
                return new_full
            _console.print(f"[bold red]❌ Ambiguous directory '{part}'. Found {len(dir_candidates)} matches.[/bold red]")
            return None
        current_check = next_check

    return file_path
