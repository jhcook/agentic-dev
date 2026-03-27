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

from agent.core.config import config

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

    1. Exact match against repo_root — return anchored path.
    2. Single unique file match in repo — auto-redirect.
    3. New file with trusted root prefix — trust the full path.
    4. New file with unknown prefix — fuzzy-search directory by directory.

    All existence checks are anchored to ``config.repo_root`` (INFRA-138),
    eliminating CWD-dependency.

    Args:
        filepath: Repo-relative file path (may be AI-generated).

    Returns:
        Resolved :class:`pathlib.Path`, or ``None`` if ambiguous/invalid.
    """
    repo_root = config.repo_root
    # Strip runbook markers that may be passed through from upstream callers
    filepath = re.sub(r"^\[(?:NEW|MODIFY|DELETE)\]\s*", "", filepath)
    # Guard: empty path after stripping resolves to repo_root (a directory) — reject early
    if not filepath.strip():
        return None
    file_path = repo_root / filepath
    if file_path.exists():
        return file_path

    # Trusted paths know exactly where they want to live — skip fuzzy search.
    is_trusted = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)
    if is_trusted:
        return repo_root / filepath

    bare_path = Path(filepath)
    if bare_path.name not in COMMON_FILES:
        candidates = _find_file_in_repo(bare_path.name)
        exact = [c for c in candidates if Path(c).name == bare_path.name]
        # Require directory overlap when the original path has parent dirs.
        # This prevents `governance/panel.py` from matching
        # `.agent/src/agent/commands/panel.py` (no shared directory component).
        if len(bare_path.parts) > 1:
            original_dirs = set(bare_path.parts[:-1])
            exact = [c for c in exact
                     if original_dirs & set(Path(c).parts[:-1])]
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
            return repo_root / new_path
        if len(exact) > 1:
            logging.debug("Ambiguous file path '%s', found %d matches", filepath, len(exact))
            return None

    parts = bare_path.parts
    current_check = repo_root

    for i, part in enumerate(parts[:-1]):
        next_check = current_check / part
        if not next_check.exists():
            logging.debug("Directory '%s' not found; searching for '%s'", next_check, part)
            dir_candidates = _find_directories_in_repo(str(part))
            if len(dir_candidates) == 0:
                logging.debug("Cannot resolve directory '%s'", part)
                return None
            if len(dir_candidates) == 1:
                rest = Path(*parts[i + 1:])
                new_full = repo_root / dir_candidates[0] / rest
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
            logging.debug("Ambiguous directory '%s', found %d matches", part, len(dir_candidates))
            return None
        current_check = next_check

    return repo_root / filepath
