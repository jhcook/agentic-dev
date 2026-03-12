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
Module for loading source code context.

Provides utilities for generating file trees and extracting source code
snippets (like imports and signatures) to give the AI context about the codebase.
"""

import logging
import os
import re as _re

from agent.core.config import config
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)

def load_source_tree() -> str:
    """Loads a file tree of the source directory for codebase context.

    Excludes __pycache__, .pyc, .env files, and other non-essential items.
    Returns an indented tree string or empty string if src/ doesn't exist.
    """
    src_dir = config.agent_dir / "src"
    if not src_dir.exists() or not src_dir.is_dir():
        return ""

    exclude_dirs = {"__pycache__", ".pytest_cache", "node_modules", ".git"}
    exclude_exts = {".pyc", ".pyo"}
    exclude_files = {".env", ".env.local", ".env.production"}

    tree = "SOURCE FILE TREE:\n"
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(src_dir):
        # Filter excluded directories in-place (os.walk respects this)
        dirnames[:] = sorted(
            d for d in dirnames if d not in exclude_dirs
        )
        rel = os.path.relpath(dirpath, config.repo_root)
        level = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * level
        if dirpath == str(src_dir):
            dirname = rel
        else:
            dirname = os.path.basename(dirpath)
        tree += f"{indent}{dirname}/\n"
        sub_indent = "  " * (level + 1)
        for fname in sorted(filenames):
            if (
                not any(fname.endswith(ext) for ext in exclude_exts)
                and fname not in exclude_files
            ):
                tree += f"{sub_indent}{fname}\n"
                file_count += 1

    logger.debug("Source tree: %d files found", file_count)
    return scrub_sensitive_data(tree)

def load_targeted_context(story_content: str) -> str:
    """Parse file paths from story and extract signatures/imports."""
    paths = set(_re.findall(
        r'(?:\[)?(?:MODIFY|NEW|DELETE|refactor|decompose)(?:\])?\s+[`"]?'
        r'([a-zA-Z0-9_/.-]+\.py)[`"]?',
        story_content, _re.IGNORECASE
    ))
    
    output = "TARGETED FILE CONTENTS:\n"
    file_count = 0
    
    for path_str in sorted(paths):
        target_path = None
        # Resolution logic
        candidates = [
            config.repo_root / path_str,
            config.agent_dir / path_str,
            config.agent_dir / "src" / path_str,
            config.agent_dir / ".agent" / "src" / path_str,
            os.path.abspath(path_str)
        ]
        for cand in candidates:
            if os.path.isfile(cand):
                target_path = cand
                break
        
        if target_path is None:
            output += f"\n--- {path_str} --- FILE NOT FOUND (verify path!)\n"
            continue

        try:
            with open(target_path, "r", errors="ignore") as f:
                content = f.read()
            rel_path = os.path.relpath(target_path, config.repo_root)
            
            # Provide the entire context inside the payload instead of just signatures
            # Truncate slightly if absolutely massive, but most files easily fit the generous budget
            if len(content) > 30000:
                lines = content.splitlines()
                head = "\n".join(lines[:300])
                tail = "\n".join(lines[-300:])
                content = f"{head}\n... ({len(lines) - 600} lines omitted) ...\n{tail}"
            
            output += f"\n--- {rel_path} ---\n{content}\n"
            file_count += 1
        except FileNotFoundError:
            logger.warning("Targeted context file not found: %s", path_str)
            output += f"\n--- {path_str} --- FILE NOT FOUND (verify path!)\n"
        except Exception as e:
            logger.error("Error reading targeted context file %s: %s", path_str, str(e))
            output += f"\n--- {path_str} --- ERROR READING FILE\n"

    result = scrub_sensitive_data(output)
    logger.debug(
        "Targeted context size: %d chars, processed %d files",
        len(result), file_count,
    )
    return result

def load_source_snippets(budget: int = 0) -> str:
    """Loads compact source outlines (imports + signatures) from Python files.

    Walks all .py files under src/, extracts import lines and
    class/def signatures (not bodies), and concatenates them until
    the character budget is exhausted.

    Args:
        budget: Maximum character count for combined snippets.
                If 0 (default), reads from AGENT_SOURCE_CONTEXT_CHAR_LIMIT
                env var, falling back to 8000.

    Returns:
        Formatted string of source outlines, or empty string if unavailable.
    """
    src_dir = config.agent_dir / "src"
    if not src_dir.exists():
        return ""

    if budget <= 0:
        budget = int(
            os.environ.get("AGENT_SOURCE_CONTEXT_CHAR_LIMIT", "16000")
        )

    exclude_dirs = {"__pycache__", ".pytest_cache"}
    # Match class/def/async def signatures, including indented and decorated
    sig_pattern = _re.compile(
        r"^[ \t]*((?:@\w+.*\n[ \t]*)*"
        r"(?:class|def|async\s+def)\s+\S+.*?):\s*$",
        _re.MULTILINE,
    )

    snippets = "SOURCE CODE OUTLINES:\n"
    remaining = budget - len(snippets)
    file_count = 0

    for py_file in sorted(src_dir.rglob("*.py")):
        # Skip excluded directories
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        # Skip trivial __init__.py files
        if py_file.name == "__init__.py" and py_file.stat().st_size < 200:
            continue

        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        try:
            rel_path = py_file.relative_to(config.repo_root)
        except ValueError:
            # Fallback if somehow not under repo root
            rel_path = py_file.relative_to(config.agent_dir)
        lines: list[str] = []

        # Imports (first 20 import lines max)
        import_lines = [
            line
            for line in content.splitlines()
            if line.startswith(("import ", "from "))
        ][:20]
        if import_lines:
            lines.extend(import_lines)

        # Class/function signatures (with optional decorators)
        for m in sig_pattern.finditer(content):
            lines.append(m.group(1))

        if not lines:
            continue

        block = f"\n--- {rel_path} ---\n" + "\n".join(lines) + "\n"

        if len(block) > remaining:
            truncated = block[: remaining - 20] + "\n[...truncated...]\n"
            snippets += truncated
            file_count += 1
            break
        snippets += block
        remaining -= len(block)
        file_count += 1

    logger.debug("Source snippets: %d files included", file_count)
    return scrub_sensitive_data(snippets)
