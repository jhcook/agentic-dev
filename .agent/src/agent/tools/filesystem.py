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
Filesystem tools for agentic workflows.

Provides operations for reading, editing, patching, creating, and moving files.
All operations are sandboxed to the repository root.
"""

import difflib
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from opentelemetry import trace

from agent.core.utils import scrub_sensitive_data
from agent.tools.utils import validate_path

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Re-export the shared helper under the legacy private name so that any
# internal callers within this module continue to work unchanged.
_validate_path = validate_path


def _stage_file(filepath: Path, repo_root: Path) -> None:
    """
    Stages a file in git if possible.

    Args:
        filepath: The path to the file to stage.
        repo_root: The repository root.
    """
    try:
        subprocess.run(
            ["git", "add", str(filepath)],
            cwd=str(repo_root),
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass


def read_file(path: str, repo_root: Path) -> str:
    """
    Reads a file from the repository, capped at 2000 lines.

    Args:
        path: Path relative to repo root.
        repo_root: Repository root path.

    Returns:
        The file content or an error message.
    """
    with tracer.start_as_current_span("tool.read_file") as span:
        span.set_attribute("tool.path", path)
        try:
            filepath = _validate_path(path, repo_root)
            if not filepath.is_file():
                return f"Error: '{path}' is not a file or does not exist."
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
            return scrub_sensitive_data(content)
        except Exception as e:
            span.record_exception(e)
            return f"Error reading file {path}: {e}"


def edit_file(path: str, content: str, repo_root: Path) -> str:
    """
    Rewrites the entire content of a file.

    Args:
        path: Path relative to repo root.
        content: New content for the file.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.edit_file") as span:
        span.set_attribute("tool.path", path)
        try:
            filepath = _validate_path(path, repo_root)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            _stage_file(filepath, repo_root)
            return f"File {path} successfully updated and staged."
        except Exception as e:
            span.record_exception(e)
            return f"Error editing file {path}: {e}"


def patch_file(path: str, search: str, replace: str, repo_root: Path) -> str:
    """
    Safely replaces a specific chunk of text in a file.

    Args:
        path: Path relative to repo root.
        search: Text to find.
        replace: Text to replace with.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.patch_file") as span:
        span.set_attribute("tool.path", path)
        try:
            filepath = _validate_path(path, repo_root)
            if not filepath.exists():
                return f"Error: File '{path}' does not exist."
            content = filepath.read_text()
            occurrences = content.count(search)
            if occurrences == 0:
                return f"Error: The search string was not found in '{path}'."
            elif occurrences > 1:
                return f"Error: The search string matches {occurrences} times. Be more specific."
            new_content = content.replace(search, replace, 1)
            filepath.write_text(new_content)
            _stage_file(filepath, repo_root)
            return f"File {path} successfully patched and staged."
        except Exception as e:
            span.record_exception(e)
            return f"Error patching file {path}: {e}"


def create_file(path: str, content: str, repo_root: Path) -> str:
    """
    Creates a new file with the given content.

    Args:
        path: Path relative to repo root.
        content: Initial content.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.create_file") as span:
        span.set_attribute("tool.path", path)
        try:
            filepath = _validate_path(path, repo_root)
            if filepath.exists():
                return f"Error: File '{path}' already exists."
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            _stage_file(filepath, repo_root)
            return f"File {path} successfully created and staged."
        except Exception as e:
            span.record_exception(e)
            return f"Error creating file {path}: {e}"


def delete_file(path: str, repo_root: Path) -> str:
    """
    Deletes a file from the repository.

    Args:
        path: Path relative to repo root.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.delete_file") as span:
        span.set_attribute("tool.path", path)
        try:
            filepath = _validate_path(path, repo_root)
            if not filepath.is_file():
                return f"Error: '{path}' is not a file."
            os.remove(filepath)
            return f"File {path} successfully deleted."
        except Exception as e:
            span.record_exception(e)
            return f"Error deleting file {path}: {e}"


def find_files(pattern: str, repo_root: Path) -> str:
    """
    Finds files matching a glob pattern.

    Args:
        pattern: Glob pattern.
        repo_root: Repository root path.

    Returns:
        Newline-separated list of matches.
    """
    with tracer.start_as_current_span("tool.find_files") as span:
        span.set_attribute("tool.pattern", pattern)
        try:
            matches = list(repo_root.rglob(pattern))
            results = [str(m.relative_to(repo_root)) for m in matches[:100]]
            return "\n".join(results) or "No files found matching that pattern."
        except Exception as e:
            span.record_exception(e)
            return f"Error finding files: {e}"


def move_file(src: str, dst: str, repo_root: Path) -> str:
    """
    Moves a file from src to dst.

    Args:
        src: Source path relative to repo root.
        dst: Destination path relative to repo root.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.move_file") as span:
        span.set_attribute("tool.src", src)
        span.set_attribute("tool.dst", dst)
        try:
            src_path = _validate_path(src, repo_root)
            dst_path = _validate_path(dst, repo_root)
            if not src_path.exists():
                return f"Error: Source '{src}' does not exist."
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            _stage_file(src_path, repo_root)
            _stage_file(dst_path, repo_root)
            return f"Successfully moved {src} to {dst}."
        except Exception as e:
            span.record_exception(e)
            return f"Error moving file: {e}"


def copy_file(src: str, dst: str, repo_root: Path) -> str:
    """
    Copies a file from src to dst.

    Args:
        src: Source path relative to repo root.
        dst: Destination path relative to repo root.
        repo_root: Repository root path.

    Returns:
        Success or error message.
    """
    with tracer.start_as_current_span("tool.copy_file") as span:
        span.set_attribute("tool.src", src)
        span.set_attribute("tool.dst", dst)
        try:
            src_path = _validate_path(src, repo_root)
            dst_path = _validate_path(dst, repo_root)
            if not src_path.exists():
                return f"Error: Source '{src}' does not exist."
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
            _stage_file(dst_path, repo_root)
            return f"Successfully copied {src} to {dst}."
        except Exception as e:
            span.record_exception(e)
            return f"Error copying file: {e}"


def file_diff(path_a: str, path_b: str, repo_root: Path) -> str:
    """
    Computes a unified diff between two files.

    Args:
        path_a: First file path.
        path_b: Second file path.
        repo_root: Repository root path.

    Returns:
        Unified diff output.
    """
    with tracer.start_as_current_span("tool.file_diff") as span:
        span.set_attribute("tool.path_a", path_a)
        span.set_attribute("tool.path_b", path_b)
        try:
            file_a = _validate_path(path_a, repo_root)
            file_b = _validate_path(path_b, repo_root)
            content_a = file_a.read_text().splitlines()
            content_b = file_b.read_text().splitlines()
            diff = difflib.unified_diff(content_a, content_b, fromfile=path_a, tofile=path_b)
            return "\n".join(diff) or "No differences found."
        except Exception as e:
            span.record_exception(e)
            return f"Error computing diff: {e}"