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

"""Orchestrator for the implement command step-execution loop (INFRA-102).

Contains block parsers, path resolution, source-context injection,
and the per-step apply+commit loop. The CLI facade delegates to
:class:`Orchestrator` after handling argument parsing.
"""

import logging
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

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
                return new_full
            _console.print(f"[bold red]❌ Ambiguous directory '{part}'. Found {len(dir_candidates)} matches.[/bold red]")
            return None
        current_check = next_check

    return file_path


def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """Parse full-file code blocks from AI-generated markdown.

    Recognises two formats::

        ```python:path/to/file.py
        code
        ```

        File: path/to/file.py
        ```python
        code
        ```

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'`` and ``'content'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    for match in re.finditer(r'```[\w]+:([\w/\.\-_]+)\n(.*?)```', content, re.DOTALL):
        blocks.append({"file": match.group(1).strip(), "content": match.group(2).strip()})
    p2 = r'(?:File|Modify|Create):\s*`?([^\n`]+)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(p2, content, re.DOTALL | re.IGNORECASE):
        fp = match.group(1).strip()
        if not any(b["file"] == fp for b in blocks):
            blocks.append({"file": fp, "content": match.group(2).strip()})
    return blocks


def parse_search_replace_blocks(content: str) -> List[Dict[str, str]]:
    """Parse search/replace blocks from AI-generated content.

    Expected format per file::

        File: path/to/file.py
        <<<SEARCH
        exact lines
        ===
        replacement lines
        >>>

    Args:
        content: Raw AI response string.

    Returns:
        List of dicts with ``'file'``, ``'search'``, ``'replace'`` keys.
    """
    blocks: List[Dict[str, str]] = []
    file_sections = re.split(
        r'(?:^|\n)(?:File|Modify):\s*`?([^\n`]+)`?\s*\n',
        content, flags=re.IGNORECASE,
    )
    for i in range(1, len(file_sections), 2):
        filepath = file_sections[i].strip()
        body = file_sections[i + 1] if i + 1 < len(file_sections) else ""
        for match in re.finditer(r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', body, re.DOTALL):
            blocks.append({"file": filepath, "search": match.group(1), "replace": match.group(2)})
    if _tracer:
        span = _tracer.start_span("implement.parse_search_replace")
        span.set_attribute("block_count", len(blocks))
        span.end()
    return blocks


def extract_modify_files(runbook_content: str) -> List[str]:
    """Scan a runbook for [MODIFY] markers and return referenced file paths.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Deduplicated list of file path strings in order of first appearance.
    """
    seen: set = set()
    result: List[str] = []
    for path in re.findall(r'\[MODIFY\]\s*`?([^\n`]+)`?', runbook_content, re.IGNORECASE):
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def build_source_context(file_paths: List[str]) -> str:
    """Build a source-context string from current file contents.

    Files exceeding SOURCE_CONTEXT_MAX_LOC are truncated to head/tail sections.

    Args:
        file_paths: Repo-relative paths to include.

    Returns:
        Formatted string containing file contents for prompt injection.
    """
    from agent.core.implement.guards import SOURCE_CONTEXT_MAX_LOC, SOURCE_CONTEXT_HEAD_TAIL

    def _inner() -> str:
        """Read, optionally truncate, and format each file."""
        parts: List[str] = []
        for filepath in file_paths:
            resolved = resolve_path(filepath)
            if not resolved or not resolved.exists():
                logging.warning("source_context_skip file=%s reason=not_found", filepath)
                continue
            try:
                content = resolved.read_text()
            except Exception as exc:
                logging.warning("source_context_skip file=%s reason=%s", filepath, exc)
                continue
            lines = content.splitlines()
            loc = len(lines)
            if loc > SOURCE_CONTEXT_MAX_LOC:
                head = "\n".join(lines[:SOURCE_CONTEXT_HEAD_TAIL])
                tail = "\n".join(lines[-SOURCE_CONTEXT_HEAD_TAIL:])
                omitted = loc - 2 * SOURCE_CONTEXT_HEAD_TAIL
                truncated = f"{head}\n... ({omitted} lines omitted) ...\n{tail}"
                parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC — truncated):\n```\n{truncated}\n```\n"
                )
            else:
                parts.append(
                    f"### Current content of `{filepath}` ({loc} LOC):\n```\n{content}\n```\n"
                )
        return "\n".join(parts)

    if _tracer:
        with _tracer.start_as_current_span("implement.inject_source_context") as span:
            span.set_attribute("file_count", len(file_paths))
            result = _inner()
            span.set_attribute("total_chars", len(result))
            return result
    return _inner()


def split_runbook_into_chunks(content: str) -> Tuple[str, List[str]]:
    """Split a runbook into a global context header and per-step chunks.

    Also appends Definition of Done and Verification Plan as trailing chunks
    so documentation and test requirements are processed by the AI.

    Args:
        content: Full runbook markdown string.

    Returns:
        Tuple of ``(global_context, list_of_step_chunks)``.
    """
    impl_headers = ["## Implementation Steps", "## Proposed Changes", "## Changes"]
    start_idx = -1
    for header in impl_headers:
        if header in content:
            start_idx = content.find(header)
            break
    if start_idx == -1:
        return content, [content]
    global_context = content[:start_idx].strip()
    body = content[start_idx:]
    raw_chunks = re.split(r'\n### ', body)
    header_part = raw_chunks[0]
    chunks: List[str] = [
        f"{header_part}\n### {raw_chunks[i]}" for i in range(1, len(raw_chunks))
    ]
    if not chunks:
        chunks = [body]
    dod = re.search(r'(## Definition of Done.*?)(?=\n## |$)', content, re.DOTALL)
    if dod:
        chunks.append(f"DOCUMENTATION AND COMPLETION REQUIREMENTS:\n{dod.group(1).strip()}")
    verify = re.search(r'(## Verification Plan.*?)(?=\n## |$)', content, re.DOTALL)
    if verify:
        chunks.append(f"TEST REQUIREMENTS:\n{verify.group(1).strip()}")
    return global_context, chunks


class Orchestrator:
    """Executes runbook steps: parse blocks, enforce guards, micro-commit.

    Delegates file writing to :mod:`agent.core.implement.guards` and LOC
    tracking/thresholds to :class:`~agent.core.implement.circuit_breaker.CircuitBreaker`.
    """

    def __init__(self, story_id: str, yes: bool = False, legacy_apply: bool = False) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []

    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        Processes search/replace blocks first, then full-file blocks.
        For each full-file block runs the docstring gate (AC-10) before
        writing. Fixes the block_loc uninitialised-variable bug (AC-9) by
        resetting ``block_loc`` to ``0`` before each apply call.

        Args:
            chunk_result: Raw AI output for this step.
            step_index: 1-based step number (for logging).

        Returns:
            Tuple of ``(step_loc, step_modified_files)``.
        """
        from agent.core.implement.guards import (
            apply_search_replace_to_file,
            apply_change_to_file,
            enforce_docstrings,
        )
        from agent.core.implement.circuit_breaker import count_edit_distance

        step_loc = 0
        step_modified_files: List[str] = []

        sr_blocks = parse_search_replace_blocks(chunk_result)
        sr_handled: set = set()
        if sr_blocks:
            sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for block in sr_blocks:
                sr_by_file[block["file"]].append(block)
            for sr_filepath, file_blocks in sr_by_file.items():
                fp = Path(sr_filepath)
                original_content = fp.read_text() if fp.exists() else ""
                success, final_content = apply_search_replace_to_file(
                    sr_filepath, file_blocks, self.yes
                )
                if success:
                    step_loc += count_edit_distance(original_content, final_content)
                    step_modified_files.append(sr_filepath)
                    sr_handled.add(sr_filepath)

        code_blocks = [b for b in parse_code_blocks(chunk_result) if b["file"] not in sr_handled]
        for block in code_blocks:
            violations = enforce_docstrings(block["file"], block["content"])
            if violations:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold red]❌ DOCSTRING GATE: {block['file']} rejected "
                    f"({len(violations)} violation(s)):[/bold red]"
                )
                for v in violations:
                    _console.print(f"   [red]• {v}[/red]")
                continue

            fp = Path(block["file"])
            original_content = fp.read_text() if fp.exists() else ""

            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            success = apply_change_to_file(
                block["file"], block["content"], self.yes,
                legacy_apply=self.legacy_apply,
            )
            if success:
                block_loc = count_edit_distance(original_content, block["content"])
                step_modified_files.append(block["file"])
            else:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold yellow]⚠️  INCOMPLETE STEP: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            step_loc += block_loc

        self.run_modified_files.extend(step_modified_files)
        return step_loc, step_modified_files

    def print_incomplete_summary(self) -> None:
        """Print the INCOMPLETE IMPLEMENTATION banner when files were rejected.

        Must be called before post-apply governance gates so the developer
        sees the full picture regardless of gate outcomes (AC-9).
        """
        if self.rejected_files:
            _console.print(
                f"\n[bold red]🚨 INCOMPLETE IMPLEMENTATION "
                f"— {len(self.rejected_files)} file(s) NOT applied:[/bold red]"
            )
            for rf in self.rejected_files:
                _console.print(f"  [red]• {rf}[/red]")
            _console.print(
                "[yellow]Hint: update runbook step(s) to use "
                "<<<SEARCH\n<exact lines>\n===\n<replacement>\n>>> blocks "
                "then re-run `agent implement`.[/yellow]"
            )
            logging.warning(
                "implement_incomplete story=%s rejected_files=%r",
                self.story_id, self.rejected_files,
            )
