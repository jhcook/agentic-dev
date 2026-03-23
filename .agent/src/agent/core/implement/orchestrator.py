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

import asyncio
import logging
import re
import subprocess
import time
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from .parser import (
    parse_code_blocks,
    parse_search_replace_blocks,
    extract_modify_files,
    extract_approved_files,
    extract_cross_cutting_files,
    detect_malformed_modify_blocks,
    validate_runbook_schema,
    split_runbook_into_chunks,
)
from .resolver import resolve_path, extract_story_id
from .retry import retry_with_backoff, MaxRetriesExceededError
from .telemetry_helper import emit_chunk_event
from agent.core.config import config

from rich.console import Console

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

_console = Console()


class ChunkStatus(Enum):
    """Execution states for an orchestration chunk."""

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


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


class Orchestrator:
    """Executes runbook steps: parse blocks, enforce guards, micro-commit.

    Delegates file writing to :mod:`agent.core.implement.guards` and LOC
    tracking/thresholds to :class:`~agent.core.implement.circuit_breaker.CircuitBreaker`.
    """

    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
        concurrency_limit: int = 4,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
            concurrency_limit: Max parallel chunk tasks (INFRA-169).
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.approved_files = approved_files
        self.cross_cutting_files = cross_cutting_files or set()
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []
        self.total_blocks: int = 0
        self.scope_violations: int = 0
        # Initialize preference from feature flag (INFRA-169)
        self.use_concurrency = config.ENABLE_CONCURRENT_ORCHESTRATION
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.chunk_states: Dict[int, ChunkStatus] = {}
        # Activate log scrubbing for implementation-related logs (INFRA-169)
        from agent.core.implement.security import apply_orchestration_filter
        apply_orchestration_filter()

    @staticmethod
    def _on_chunk_retry(attempt: int, exc: Exception, self_ref: "Orchestrator", chunk_result: str, step_index: int) -> None:
        """Emit structured telemetry for chunk retry events."""
        from agent.core.implement.security import sanitize_error_message
        emit_chunk_event(
            "chunk_retry", self_ref.story_id, step_index,
            error=sanitize_error_message(exc), attempt=attempt,
        )

    @staticmethod
    def _on_chunk_failure(attempts: int, exc: Exception, self_ref: "Orchestrator", chunk_result: str, step_index: int) -> None:
        """Emit structured telemetry for permanent chunk failure."""
        from agent.core.implement.security import sanitize_error_message
        emit_chunk_event(
            "chunk_failure", self_ref.story_id, step_index,
            error=sanitize_error_message(exc), attempt=attempts,
        )

    @retry_with_backoff(
        max_retries=3, base_delay=1.0,
        on_retry=_on_chunk_retry.__func__,
        on_failure=_on_chunk_failure.__func__,
    )
    async def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        This is an ``async`` coroutine decorated with ``@retry_with_backoff``
        (max 3 retries, exponential backoff). On permanent failure it raises
        :class:`~agent.core.implement.retry.MaxRetriesExceededError`.

        Processes search/replace blocks first, then full-file blocks.
        For each full-file block runs the docstring gate (AC-10) before
        writing. Fixes the block_loc uninitialised-variable bug (AC-9) by
        resetting ``block_loc`` to ``0`` before each apply call.

        Wraps execution in a Langfuse/OTLP trace span (INFRA-136 AC-1).

        Args:
            chunk_result: Raw AI output for this step.
            step_index: 1-based step number (for logging).

        Returns:
            Tuple of ``(step_loc, step_modified_files)``.

        Raises:
            MaxRetriesExceededError: If all retry attempts are exhausted.
        """
        start_time = time.perf_counter()
        emit_chunk_event("chunk_start", self.story_id, step_index)

        span = None
        if _tracer:
            span = _tracer.start_span("implement.apply_chunk")
            span.set_attribute("story_id", self.story_id)
            span.set_attribute("step_index", step_index)

        from agent.core.implement.guards import (
            apply_search_replace_to_file,
            apply_change_to_file,
            enforce_docstrings,
        )
        from agent.core.implement.circuit_breaker import count_edit_distance

        step_loc = 0
        step_modified_files: List[str] = []

        # Detect malformed runbook blocks before applying: a [MODIFY] header with
        # a full code block but no <<<SEARCH blocks is silently unreachable.
        # Surface this loudly so the developer knows to fix the runbook.
        malformed = detect_malformed_modify_blocks(chunk_result)
        for mf in malformed:
            _console.print(
                f"[bold yellow]⚠️  RUNBOOK FORMAT ERROR: '[MODIFY] {mf}' has a full "
                f"code block but no <<<SEARCH blocks — this file will be SKIPPED.\n"
                f"   Fix: replace the code block with <<<SEARCH/===/>>> blocks.[/bold yellow]"
            )
            logging.warning(
                "malformed_modify_block file=%s step=%d", mf, step_index
            )

        sr_blocks = parse_search_replace_blocks(chunk_result)
        sr_handled: set = set()
        if sr_blocks:
            sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for block in sr_blocks:
                sr_by_file[block["file"]].append(block)
            for sr_filepath, file_blocks in sr_by_file.items():
                self.total_blocks += 1
                if not self._check_scope(sr_filepath, step_index):
                    continue
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
                original_content = await asyncio.to_thread(lambda: fp.read_text() if fp.exists() else "")
                success, final_content = await asyncio.to_thread(
                    apply_search_replace_to_file, 
                    sr_filepath, file_blocks, self.yes
                )
                if success:
                    step_loc += count_edit_distance(original_content, final_content)
                    step_modified_files.append(sr_filepath)
                    sr_handled.add(sr_filepath)

        code_blocks = [b for b in parse_code_blocks(chunk_result) if b["file"] not in sr_handled]
        for block in code_blocks:
            self.total_blocks += 1
            if not self._check_scope(block["file"], step_index):
                continue
            violations = enforce_docstrings(block["file"], block["content"])
            if violations:
                _console.print(
                    f"[yellow]⚠️  DOCSTRING GATE: {block['file']} "
                    f"({len(violations)} violation(s)):[/yellow]"
                )
                for v in violations:
                    _console.print(f"   [yellow]• {v}[/yellow]")
                _console.print(
                    "[dim]File will be written — fix before preflight.[/dim]"
                )

            fp = resolve_path(block["file"]) or Path(block["file"])
            original_content = await asyncio.to_thread(lambda: fp.read_text() if fp.exists() else "")

            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            
            from agent.core.implement.guards import FileSizeGuardViolation
            try:
                success = await asyncio.to_thread(
                    apply_change_to_file,
                    block["file"], block["content"], self.yes,
                    legacy_apply=self.legacy_apply,
                )
            except FileSizeGuardViolation as e:
                success = False
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold red]❌ SIZE GUARD GATE: {block['file']} rejected. "
                    f"{str(e)}[/bold red]"
                )
                
            if success:
                block_loc = count_edit_distance(original_content, block["content"])
                step_modified_files.append(block["file"])
            elif block["file"] not in self.rejected_files:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold yellow]⚠️  INCOMPLETE STEP: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            step_loc += block_loc

        self.run_modified_files.extend(step_modified_files)
        duration = time.perf_counter() - start_time
        
        emit_chunk_event(
            "chunk_success", 
            self.story_id, 
            step_index, 
            duration=duration, 
            modified_files=step_modified_files
        )

        if span:
            span.set_attribute("duration_sec", duration)
            span.set_attribute("files_modified", len(step_modified_files))
            span.set_attribute("scope_violations", self.scope_violations)
            span.set_attribute("hallucination_rate", self.get_hallucination_rate())
            span.end()

        return step_loc, step_modified_files

    def _check_scope(self, filepath: str, step_index: int) -> bool:
        """Check if a file is within the approved scope (AC-2, AC-4, AC-5).

        Args:
            filepath: Repo-relative file path being modified.
            step_index: 1-based step number for logging.

        Returns:
            True if the file is approved, False if scope-violated.
        """
        if self.approved_files is None:
            return True  # No approved set → no scope enforcement
        if filepath in self.approved_files or filepath in self.cross_cutting_files:
            return True
        self.scope_violations += 1
        self.rejected_files.append(filepath)
        _console.print(
            f"[bold red]🚫 SCOPE VIOLATION: '{filepath}' is not declared in the "
            f"runbook (step {step_index}). Skipping.[/bold red]"
        )
        logging.warning(
            "scope_violation file=%s step=%d story=%s approved_files=%r",
            filepath, step_index, self.story_id,
            sorted(self.approved_files) if self.approved_files else [],
        )
        return False

    def get_hallucination_rate(self) -> float:
        """Compute the hallucination rate (AC-3).

        Returns:
            Ratio of scope violations to total blocks, or 0.0 if no blocks.
        """
        if self.total_blocks == 0:
            return 0.0
        return self.scope_violations / self.total_blocks

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
                "[yellow]Hint: Review the specific rejection reasons above. You may need to add "
                "missing docstrings or use <<<SEARCH/===/>>> blocks for large file mutations.[/yellow]"
            )
            logging.warning(
                "implement_incomplete story=%s rejected_files=%r",
                self.story_id, self.rejected_files,
            )

    async def apply_chunks_parallel(self, chunks: List[str]) -> List[Tuple[int, List[str]]]:
        """Process multiple chunks concurrently using a semaphore.

        Args:
            chunks: List of raw AI-generated chunk strings.

        Returns:
            List of (step_loc, step_modified_files) for each chunk.
        """
        async def _bounded_apply(chunk: str, idx: int):
            async with self.semaphore:
                return await self.apply_chunk(chunk, idx)

        tasks = [
            _bounded_apply(chunk, i + 1)
            for i, chunk in enumerate(chunks)
        ]
        return await asyncio.gather(*tasks)
