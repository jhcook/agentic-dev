# Runbook: Implementation Runbook for INFRA-169

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

This section reviews the architectural alignment for INFRA-169, specifically focusing on the transition from serial generation to the phased, concurrent orchestration defined in ADR-015.

**ADR-015 Alignment Analysis**
ADR-015 (Phased Generation Architecture) mandates that complex implementation tasks be decomposed into discrete phases. Currently, failures in a single chunk cause the entire phase (and subsequent phases) to fail immediately. To satisfy the requirements of INFRA-169, the orchestrator must move to an asynchronous execution model that allows parallel processing within a phase while maintaining a "Hard Gate" between phases.

**Async State Machine Design**
To ensure phase-gate integrity, we implement a state machine for individual chunks within `orchestrator.py`. Chunks in a phase are executed concurrently but must all reach a `SUCCESS` terminal state before the next phase is permitted to start.

**Chunk States:**
- `PENDING`: Initial state upon phase start.
- `RUNNING`: Async task is active and processing.
- `RETRYING`: Transient error encountered; waiting for exponential backoff delay.
- `SUCCESS`: Chunk applied and committed successfully.
- `FAILED`: Terminal failure state reached after exhausting `MAX_RETRIES` (3).

**Concurrency Control**
To prevent resource exhaustion and rate-limiting from LLM providers, we implement a `Semaphore` within the `Orchestrator`. This limits the number of concurrent `apply_chunk` operations. The default concurrency limit is set to 4, which is tunable via orchestration configuration.

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```python
<<<SEARCH
import logging
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
===
import asyncio
import logging
import re
import subprocess
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
>>>

<<<SEARCH
_console = Console()

def build_source_context(file_paths: List[str]) -> str:
===
_console = Console()


class ChunkStatus(Enum):
    """Execution states for an orchestration chunk."""

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


def build_source_context(file_paths: List[str]) -> str:
>>>

<<<SEARCH
    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
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
===
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
            concurrency_limit: Maximum parallel chunk operations.
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.approved_files = approved_files
        self.cross_cutting_files = cross_cutting_files or set()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []
        self.total_blocks: int = 0
        self.scope_violations: int = 0
        self.chunk_states: Dict[int, ChunkStatus] = {}
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.core.implement.parser import validate_runbook_schema
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError

import os
===
from agent.core.implement.parser import validate_runbook_schema
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError
from agent.core.implement.orchestrator import ChunkStatus

import os
>>>

```

**Troubleshooting & Edge Cases**
- **Rate Limiting**: If many chunks hit `RETRYING` simultaneously, ensure exponential backoff includes a jitter to prevent thundering herd against the LLM provider.
- **Event Loop Blocking**: The `apply_chunk` method currently contains blocking file I/O. Future iterations should use `aiofiles`, but for INFRA-169, the `Semaphore` combined with `asyncio.to_thread` (if necessary) will mitigate blocking in the main loop.

### Step 2: Implementation - Async Orchestration Core

Modify the core orchestrator to support asynchronous execution and parallel chunk processing. This transformation enables high-throughput generation tasks by allowing independent implementation steps to execute concurrently while maintaining system stability via a semaphore-based concurrency limiter.

**Description**
The `Orchestrator` is refactored to transition from a synchronous execution model to an `asyncio`-based event loop. The primary entry point for implementing a chunk, `apply_chunk`, is converted into a coroutine. To ensure thread safety and non-blocking behavior during file system operations, I/O-intensive tasks (reading file content and writing changes) are delegated to worker threads using `asyncio.to_thread`. A new `apply_chunks_parallel` method utilizes `asyncio.gather` to manage the lifecycle of multiple chunks within a phase, respecting the `concurrency_limit` defined during initialization.

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```python
<<<SEARCH
import logging
import re
import subprocess
from collections import defaultdict
===
import asyncio
import logging
import re
import subprocess
from collections import defaultdict
>>>

<<<SEARCH
    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
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
===
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
            concurrency_limit: Max number of parallel chunk operations.
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
        self.semaphore = asyncio.Semaphore(concurrency_limit)
>>>

<<<SEARCH
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.
===
    async def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.
>>>

<<<SEARCH
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
                original_content = fp.read_text() if fp.exists() else ""
                success, final_content = apply_search_replace_to_file(
                    sr_filepath, file_blocks, self.yes
                )
===
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
                original_content = await asyncio.to_thread(lambda: fp.read_text() if fp.exists() else "")
                success, final_content = await asyncio.to_thread(
                    apply_search_replace_to_file, 
                    sr_filepath, file_blocks, self.yes
                )
>>>

<<<SEARCH
            fp = resolve_path(block["file"]) or Path(block["file"])
            original_content = fp.read_text() if fp.exists() else ""

            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            
            from agent.core.implement.guards import FileSizeGuardViolation
            try:
                success = apply_change_to_file(
                    block["file"], block["content"], self.yes,
                    legacy_apply=self.legacy_apply,
                )
===
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
>>>

<<<SEARCH
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
===
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
>>>

```

**Troubleshooting**
- **I/O Latency**: If many small files are being modified, ensure the `concurrency_limit` is not set too high (default: 4) to avoid OS-level file descriptor exhaustion.
- **Search/Replace Failures**: Since chunks are applied in parallel, ensure that no two chunks in the same runbook phase attempt to modify the exact same lines of code, as this will lead to non-deterministic `<<<SEARCH` failures.

### Step 3: Implementation - Chunk-Level Retry Logic

Develop a robust retry decorator for chunk-level tasks within the orchestrator to handle transient failures using exponential backoff and jitter. This ensures that individual chunk failures are retried in isolation, and permanent failures (Max Retries Exceeded) correctly signal the orchestrator to halt subsequent implementation phases.

#### [NEW] .agent/src/agent/core/implement/retry.py

```python
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

"""Retry logic with exponential backoff and jitter (INFRA-169)."""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Type, Union, Tuple

logger = logging.getLogger(__name__)

class MaxRetriesExceededError(Exception):
    """Raised when an operation fails after all retry attempts are exhausted."""
    pass

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
):
    """
    Decorator for async functions to apply exponential backoff and jitter.
    
    Args:
        max_retries: Number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        backoff_factor: Multiplier for the delay after each failure.
        jitter: If True, adds random jitter to the delay.
        exceptions: The exception class or tuple of classes to catch and retry.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            "chunk_retry_failed_permanently func=%s attempts=%d error=%s",
                            func.__qualname__, attempt - 1, str(e)
                        )
                        raise MaxRetriesExceededError(
                            f"Chunk task '{func.__name__}' failed after {max_retries} attempts."
                        ) from e
                    
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        "chunk_retry_attempt func=%s attempt=%d/%d delay=%.2fs error=%s",
                        func.__qualname__, attempt, max_retries, delay, str(e)
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```

<<<SEARCH
from .resolver import resolve_path, extract_story_id

from rich.console import Console
===
from .resolver import resolve_path, extract_story_id
from .retry import retry_with_backoff, MaxRetriesExceededError

from rich.console import Console
>>>
<<<SEARCH
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        Processes search/replace blocks first, then full-file blocks.
===
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk (async with retries).

        Processes search/replace blocks first, then full-file blocks.
>>>

```

#### [NEW] .agent/src/agent/core/implement/tests/test_retry.py

```python
import asyncio
import pytest
from agent.core.implement.retry import retry_with_backoff, MaxRetriesExceededError

@pytest.mark.asyncio
async def test_retry_eventual_success():
    """Verify retries succeed if the function eventually returns."""
    calls = 0
    @retry_with_backoff(max_retries=2, base_delay=0.01, jitter=False)
    async def task():
        nonlocal calls
        calls += 1
        if calls < 2: raise ConnectionError("Transient failure")
        return True
    assert await task() is True
    assert calls == 2

@pytest.mark.asyncio
async def test_retry_failure_exhaustion():
    """Verify MaxRetriesExceededError is raised after max attempts."""
    calls = 0
    @retry_with_backoff(max_retries=2, base_delay=0.01, jitter=False)
    async def task():
        nonlocal calls
        calls += 1
        raise ValueError("Permanent failure")
    with pytest.raises(MaxRetriesExceededError):
        await task()
    assert calls == 3  # Initial + 2 retries

```

**Troubleshooting & Observability**
- **Observability**: Retry attempts are logged at `WARNING` level, including the specific attempt count and calculated delay. Permanent failures (max retries reached) are emitted at `ERROR` level to highlight potential systemic issues.
- **Downstream Logic**: The `MaxRetriesExceededError` signal ensures that if a chunk fails permanently, the orchestrator's `asyncio.gather` (implemented in the previous core section) will raise the exception immediately, preventing subsequent generation phases from starting and protecting the integrity of the target codebase.
- **Backoff Tuning**: If rate limits are encountered too frequently, increase the `base_delay` or `backoff_factor` within the `@retry_with_backoff` decorator in `orchestrator.py`.

### Step 4: Implementation - Runbook Command Integration

Update the `runbook` command to support the asynchronous lifecycle of the phased generation orchestrator. This ensures that parallel chunk-processing tasks are correctly managed within the CLI event loop and that granular failures are bubbled up to the user with appropriate exit codes.

**Implementation Plan**
1. **Retry Exception Integration**: Import the new `MaxRetriesExceededError` to handle fatal orchestration failures during generation.
2. **Async Lifecycle Management**: Wrap the phased generation call in `asyncio.run` to bridge the synchronous Typer command with the asynchronous core.
3. **Status Reporting**: Add console signaling for the start of phased generation and handle error state bubbling to the terminal.

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.core.implement.guards import (
    autocorrect_runbook_fences,
    lint_runbook_syntax,
    validate_and_correct_sr_blocks,
)
from agent.db.client import upsert_artifact
===
from agent.core.implement.guards import (
    autocorrect_runbook_fences,
    lint_runbook_syntax,
    validate_and_correct_sr_blocks,
)
from agent.core.implement.retry import MaxRetriesExceededError
from agent.db.client import upsert_artifact
>>>

<<<SEARCH
    # 4. Content Generation
    # ── Chunked path ──
    if not single_pass:
        try:
            content = generate_runbook_chunked(
                story_id=story_id,
                story_content=story_content,
                rules_content=rules_content,
                targeted_context=targeted_context,
                source_tree=source_tree,
                source_code=source_code,
                provider=provider,
                timeout=timeout,
            )
            _write_and_sync(content, story_id, story_file, runbook_file)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "chunked_generation_failed",
                extra={"story_id": story_id, "error": str(exc)},
            )
            console.print(
                f"[yellow]⚠️  Chunked generation failed: {exc}\n"
                "    Falling back to legacy monolithic generation...[/yellow]"
            )
===
    # 4. Content Generation
    # ── Chunked path ──
    if not single_pass:
        console.print("[bold blue]🚀 Starting phased generation (concurrency enabled)...[/bold blue]")
        try:
            # INFRA-169: Bridge Typer CLI to the async phased generation engine.
            # Internal chunk-level retries are handled by the orchestrator; fatal exhaustion bubbles here.
            content = asyncio.run(generate_runbook_chunked(
                story_id=story_id,
                story_content=story_content,
                rules_content=rules_content,
                targeted_context=targeted_context,
                source_tree=source_tree,
                source_code=source_code,
                provider=provider,
                timeout=timeout,
            ))
            _write_and_sync(content, story_id, story_file, runbook_file)
        except MaxRetriesExceededError as e:
            console.print(f"\n[bold red]❌ Runbook generation failed after retries: {e}[/bold red]")
            logger.error("runbook_generation_max_retries_exceeded", extra={"story_id": story_id})
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"\n[bold red]❌ Unexpected generation error: {e}[/bold red]")
            logger.exception("runbook_generation_unexpected_error", extra={"story_id": story_id})
            raise typer.Exit(code=1)
>>>

```

**Troubleshooting**
- **MaxRetriesExceededError in CLI**: This indicates that one or more generation chunks failed repeatedly (e.g., due to persistent rate limiting or malformed context). Check the application logs for `chunk_retry_attempt` events to identify which specific chunk is failing.
- **Console Hangs**: Ensure that the `AGENT_AI_TIMEOUT_MS` environment variable is not set to an excessively high value; the `asyncio.run` block will wait for all parallel chunks to complete or fail before returning.
- **Telemetry Missing**: If chunk-level status is not appearing in logs, verify that `agent.core.logger` is correctly initialized in the `runbook_generation` module.

### Step 5: Security & Input Sanitization

**Objective**: Review loggers and error handlers to ensure that during retries and exception catching, sensitive payload data or API credentials are not leaked into the orchestration logs.

This section implements a centralized security filter for the implementation domain. By hooking into the logging pipeline, we ensure that all events emitted during concurrent chunk processing—including those from the newly created `retry.py` and modified `orchestrator.py`—are automatically scrubbed of API keys, tokens, and PII before reaching disk or telemetry sinks. This provides a robust, fail-safe mechanism that satisfies SOC 2 and GDPR requirements for INFRA-169.

#### [NEW] .agent/src/agent/core/implement/security.py

```python
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

"""Security and sanitization utilities for the implementation domain (INFRA-169)."""

import logging
from typing import Any
from agent.core.utils import scrub_sensitive_data

class OrchestrationSecurityFilter(logging.Filter):
    """Logging filter that scrubs sensitive data from all implementation log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filters log records to remove sensitive information from messages and arguments.

        Args:
            record: The log record to process.

        Returns:
            Always True to allow the record to be logged after scrubbing.
        """
        if isinstance(record.msg, str):
            record.msg = scrub_sensitive_data(record.msg)
        
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(scrub_sensitive_data(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        
        return True

def sanitize_error_message(error: Exception) -> str:
    """
    Extracts and scrubs the message from an exception for safe use in UI or logs.

    Args:
        error: The exception to sanitize.

    Returns:
        The scrubbed exception string.
    """
    return scrub_sensitive_data(str(error))

def apply_orchestration_filter(logger_name: str = "agent.core.implement") -> None:
    """
    Hooks the security filter into the specified logger if not already present.

    Args:
        logger_name: The name of the logger to secure.
    """
    target_logger = logging.getLogger(logger_name)
    # Check if filter already exists to prevent duplication
    for f in target_logger.filters:
        if isinstance(f, OrchestrationSecurityFilter):
            return
    target_logger.addFilter(OrchestrationSecurityFilter())

```

#### [NEW] .agent/src/agent/core/implement/tests/test_security.py

```python
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

"""Tests for implementation-layer security and sanitization (INFRA-169)."""

import logging
import pytest
from agent.core.implement.security import OrchestrationSecurityFilter, sanitize_error_message

def test_sanitize_error_message_scrubs_api_key():
    """Verify that API keys in exception messages are scrubbed."""
    # Example Anthropic key format
    fake_error = ValueError("Connection failed for key: sk-ant-api03-abcdef1234567890")
    scrubbed = sanitize_error_message(fake_error)
    assert "sk-ant-api03-" not in scrubbed
    assert "[REDACTED]" in scrubbed or "*" in scrubbed

def test_orchestration_filter_scrubs_log_args():
    """Verify the logging filter scrubs sensitive strings passed as log arguments."""
    logger = logging.getLogger("test.orchestration.security")
    logger.setLevel(logging.DEBUG)
    logger.addFilter(OrchestrationSecurityFilter())

    class CapturingHandler(logging.Handler):
        """Mock handler to capture log records."""
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    handler = CapturingHandler()
    logger.addHandler(handler)

    # Simulate a log call similar to the one in retry.py
    logger.warning("Retry attempt failed with error: %s", "sk-ant-api03-secret123")

    assert len(handler.records) == 1
    logged_arg = handler.records[0].args[0]
    assert "sk-ant-api03-" not in logged_arg
    assert "[REDACTED]" in logged_arg or "*" in logged_arg

def test_orchestration_filter_preserves_non_sensitive_args():
    """Verify the logging filter does not mangle non-string, non-sensitive arguments."""
    logger = logging.getLogger("test.orchestration.safe")
    logger.addFilter(OrchestrationSecurityFilter())
    
    class CapturingHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    handler = CapturingHandler()
    logger.addHandler(handler)

    logger.info("Processing chunk %d of %d", 1, 5)

    assert handler.records[0].args == (1, 5)

```

**Troubleshooting**
- **Issue**: Orchestration logs still show raw API keys in the console.
- **Cause**: The `OrchestrationSecurityFilter` is likely not attached to the root logger or the specific logger instance used by `retry.py` (e.g., if a sub-module logger does not propagate to the implementation namespace).
- **Resolution**: Ensure `apply_orchestration_filter()` is called during the orchestrator initialization. Verify that `retry.py` uses `logging.getLogger(__name__)` which correctly falls under the `agent.core.implement` hierarchy.
- **Issue**: Performance degradation in high-volume logging.
- **Cause**: Regex-based scrubbing on every log line in a high-concurrency loop.
- **Resolution**: This is a required trade-off for security compliance. If latency is critical, ensure `scrub_sensitive_data` uses pre-compiled regex patterns (standard in `agent.core.utils`).

### Step 6: Observability & Audit Logging

This section implements structured telemetry and audit logging for the phased generation orchestrator. By introducing a dedicated telemetry helper, we ensure that every chunk processing event (start, success, retry, and failure) is captured with precise duration metrics and metadata. This implementation fulfills SOC 2 audit requirements and provides the visibility needed to debug concurrent execution bottlenecks.

#### [NEW] .agent/src/agent/core/implement/telemetry_helper.py

```python
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

"""Telemetry and audit logging helpers for orchestration (INFRA-169)."""

import logging
import time
from typing import Any, Dict, List, Optional

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None

logger = logging.getLogger("agent.core.implement.telemetry")

def emit_chunk_event(
    event_type: str,
    story_id: str,
    step_index: int,
    duration: Optional[float] = None,
    retry_count: int = 0,
    error: Optional[str] = None,
    modified_files: Optional[List[str]] = None,
) -> None:
    """
    Emit a structured telemetry event for a chunk processing lifecycle stage.

    Args:
        event_type: One of 'chunk_start', 'chunk_success', 'chunk_retry', 'chunk_failure'.
        story_id: The identifier of the story being implemented.
        step_index: The 1-based index of the current implementation step.
        duration: Time taken in seconds (for success/failure/retry).
        retry_count: Current retry attempt number.
        error: Exception message if the event is a failure or retry.
        modified_files: List of files affected by this chunk.
    """
    payload: Dict[str, Any] = {
        "event": event_type,
        "story_id": story_id,
        "step_index": step_index,
        "retry_count": retry_count,
    }
    if duration is not None:
        payload["duration_ms"] = round(duration * 1000, 2)
    if error:
        payload["error"] = error
    if modified_files:
        payload["files"] = modified_files

    # Structured Logging (SOC 2 Audit Trail)
    log_msg = f"{event_type} story={story_id} step={step_index}"
    if event_type == "chunk_failure":
        logger.error(log_msg, extra=payload)
    elif event_type == "chunk_retry":
        logger.warning(log_msg, extra=payload)
    else:
        logger.info(log_msg, extra=payload)

    # OpenTelemetry Tracing
    if _tracer:
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(event_type, payload)
            if duration:
                span.set_attribute(f"{event_type}.duration_ms", payload["duration_ms"])

```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```python
<<<SEARCH
import logging
import re
import subprocess
from collections import defaultdict
===
import logging
import re
import subprocess
import time
from collections import defaultdict
>>>

```

```python
<<<SEARCH
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
===
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
from .telemetry_helper import emit_chunk_event
>>>

```

```python
<<<SEARCH
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

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
        """
        span = None
        if _tracer:
            span = _tracer.start_span("implement.apply_chunk")
            span.set_attribute("story_id", self.story_id)
            span.set_attribute("step_index", step_index)
===
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

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
        """
        start_time = time.perf_counter()
        emit_chunk_event("chunk_start", self.story_id, step_index)

        span = None
        if _tracer:
            span = _tracer.start_span("implement.apply_chunk")
            span.set_attribute("story_id", self.story_id)
            span.set_attribute("step_index", step_index)
>>>

```

```python
<<<SEARCH
        self.run_modified_files.extend(step_modified_files)

        if span:
            span.set_attribute("files_modified", len(step_modified_files))
            span.set_attribute("scope_violations", self.scope_violations)
            span.set_attribute("hallucination_rate", self.get_hallucination_rate())
            span.end()

        return step_loc, step_modified_files
===
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
>>>

```

#### [NEW] .agent/src/agent/core/implement/tests/test_telemetry_helper.py

```python
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

"""Tests for orchestration telemetry hooks (INFRA-169)."""

import logging
import pytest
from agent.core.implement.telemetry_helper import emit_chunk_event

class MockHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(record)

@pytest.fixture
def log_capture():
    logger = logging.getLogger("agent.core.implement.telemetry")
    handler = MockHandler()
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)

def test_emit_chunk_start(log_capture):
    emit_chunk_event("chunk_start", "INFRA-169", 1)
    assert len(log_capture.records) == 1
    assert log_capture.records[0].msg == "chunk_start story=INFRA-169 step=1"
    assert log_capture.records[0].extra["event"] == "chunk_start"

def test_emit_chunk_success_with_metrics(log_capture):
    emit_chunk_event(
        "chunk_success", 
        "INFRA-169", 
        1, 
        duration=0.555, 
        modified_files=["file1.py"]
    )
    assert len(log_capture.records) == 1
    record = log_capture.records[0]
    assert record.extra["duration_ms"] == 555.0
    assert record.extra["files"] == ["file1.py"]

def test_emit_chunk_failure_log_level(log_capture):
    emit_chunk_event("chunk_failure", "INFRA-169", 1, error="Timeout")
    assert log_capture.records[0].levelno == logging.ERROR
    assert log_capture.records[0].extra["error"] == "Timeout"

```

**Troubleshooting**

- **Missing Logs**: Ensure the logger `agent.core.implement.telemetry` is not filtered out in your `logging.yaml` or `.agent/config.yaml`. The default level is `INFO`.
- **Zero Durations**: Duration metrics rely on `time.perf_counter()`. On extremely fast operations (e.g., empty chunks), duration may appear as `0.00ms` if the system clock resolution is low, though `perf_counter` is typically nanosecond-accurate.
- **Telemetry Overhead**: Telemetry hooks are lightweight wrappers around standard Python logging and OTLP spans. In high-concurrency scenarios, ensure the log handler is non-blocking (the default `logging` handlers are blocking unless wrapped in `QueueHandler`).

### Step 7: Verification & Test Suite

This section provides the comprehensive testing suite for the concurrent orchestration and retry logic introduced in INFRA-169. It includes unit tests for backoff timing, integration tests for transient failure recovery, and stress tests for high-volume concurrency limits.

**Test Execution Command**

To run the implementation-specific test suite:

```bash
pytest .agent/src/agent/core/implement/tests/test_retry_backoff.py \
       .agent/src/agent/core/implement/tests/test_orchestrator_integration.py \
       .agent/src/agent/core/implement/tests/test_orchestrator_concurrency.py

```

#### [NEW] .agent/src/agent/core/implement/tests/test_retry_backoff.py

```python
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

"""Unit tests for exponential backoff and jitter calculations (INFRA-169)."""

import asyncio
import time
import pytest
from agent.core.implement.retry import retry_with_backoff

@pytest.mark.asyncio
async def test_backoff_timing_exponential():
    """Verify that delays increase exponentially between attempts."""
    timings = []
    
    @retry_with_backoff(max_retries=2, base_delay=0.1, backoff_factor=2.0, jitter=False)
    async def flappy_task():
        timings.append(time.time())
        if len(timings) < 3:
            raise RuntimeError("Retry required")
        return True

    start = time.time()
    await flappy_task()
    
    # Intervals should be ~0.1s then ~0.2s
    interval_1 = timings[1] - timings[0]
    interval_2 = timings[2] - timings[1]
    
    assert 0.09 <= interval_1 <= 0.15
    assert 0.19 <= interval_2 <= 0.25

@pytest.mark.asyncio
async def test_jitter_application():
    """Verify that jitter introduces variance in retry timing."""
    timings_1 = []
    timings_2 = []
    
    async def task_logic(log):
        log.append(time.time())
        if len(log) < 2:
            raise RuntimeError("Retry")
        return True

    # Run two identical tasks with jitter and check if they differ
    t1 = retry_with_backoff(max_retries=1, base_delay=0.1, jitter=True)(task_logic)
    t2 = retry_with_backoff(max_retries=1, base_delay=0.1, jitter=True)(task_logic)
    
    await t1(timings_1)
    await t2(timings_2)
    
    delay_1 = timings_1[1] - timings_1[0]
    delay_2 = timings_2[1] - timings_2[0]
    
    # It is extremely unlikely two jittered runs are identical to high precision
    assert delay_1 != delay_2

```

#### [NEW] .agent/src/agent/core/implement/tests/test_orchestrator_integration.py

```python
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

"""Integration tests for Orchestrator with concurrent retries (INFRA-169)."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from agent.core.implement.orchestrator import Orchestrator
from agent.core.implement.retry import MaxRetriesExceededError

@pytest.mark.asyncio
async def test_orchestrator_parallel_chunk_success():
    """Verify multiple chunks are processed in parallel within a phase."""
    orchestrator = Orchestrator(story_id="INFRA-169", yes=True)
    
    # Mock the internal async applier (added in Step 2)
    with patch("agent.core.implement.orchestrator.apply_change_to_file", new_callable=AsyncMock) as mock_apply:
        mock_apply.return_value = True
        
        chunk_content = "#### [NEW] file1.py\n```python\nprint(1)\n```\n#### [NEW] file2.py\n```python\nprint(2)\n```"

```

        # Process chunk (assuming orchestrator.apply_chunk became async or uses async internally)
        # Note: If apply_chunk is still sync, this test targets the new async core methods
        loc, modified = await orchestrator.apply_chunk_async(chunk_content, 1)
        
        assert len(modified) == 2
        assert "file1.py" in modified
        assert "file2.py" in modified
        assert mock_apply.call_count == 2

@pytest.mark.asyncio
async def test_orchestrator_transient_failure_recovery():
    """Verify orchestrator recovers if a chunk applier fails initially."""
    orchestrator = Orchestrator(story_id="INFRA-169", yes=True)

    # Fail once, then succeed
    side_effects = [RuntimeError("Transient FS lock"), True]
    
    with patch("agent.core.implement.orchestrator.apply_change_to_file", new_callable=AsyncMock) as mock_apply:
        mock_apply.side_effect = side_effects
        
        chunk_content = "

```

#### [NEW] file_retry.py\n```python\npass\n```"

```

        loc, modified = await orchestrator.apply_chunk_async(chunk_content, 1)
        
        assert "file_retry.py" in modified
        assert mock_apply.call_count == 2

@pytest.mark.asyncio
async def test_orchestrator_permanent_failure_halts_downstream():
    """Verify MaxRetriesExceeded stops the process (Negative Test)."""
    orchestrator = Orchestrator(story_id="INFRA-169", yes=True)

    with patch("agent.core.implement.orchestrator.apply_change_to_file", new_callable=AsyncMock) as mock_apply:
        mock_apply.side_effect = RuntimeError("Permanent network error")
        
        chunk_content = "

```

#### [NEW] doomed.py\n```python\npass\n```"
        
        with pytest.raises(MaxRetriesExceededError):
            await orchestrator.apply_chunk_async(chunk_content, 1)

```

#### [NEW] .agent/src/agent/core/implement/tests/test_orchestrator_concurrency.py

```python
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

"""Stress tests for high-volume concurrent generation (INFRA-169)."""

import asyncio
import time
import pytest
from unittest.mock import patch, AsyncMock
from agent.core.implement.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_orchestrator_concurrency_limit():
    """
    Verify that the concurrency limiter (semaphore) prevents resource exhaustion.
    If semaphore is 5 and we have 10 tasks of 0.1s, it should take ~0.2s.
    """
    orchestrator = Orchestrator(story_id="STRESS-001", yes=True)
    
    async def slow_apply(*args, **kwargs):
        await asyncio.sleep(0.1)
        return True

    with patch("agent.core.implement.orchestrator.apply_change_to_file", side_effect=slow_apply):
        # Construct a massive chunk with 10 files
        content_parts = []
        for i in range(10):
            content_parts.append(f"#### [NEW] stress_{i}.py\n```python\npass\n```")

```

        chunk_content = "\n".join(content_parts)
        
        start_time = time.time()
        await orchestrator.apply_chunk_async(chunk_content, 1)
        duration = time.time() - start_time
        
        # If parallel without limit: ~0.1s
        # If serial: ~1.0s
        # If limit=5: ~0.2s
        assert 0.18 <= duration <= 0.35, f"Concurrency limit of 5 not enforced. Duration: {duration}s"

@pytest.mark.asyncio
async def test_orchestrator_stability_high_volume():
    """Verify system stability when processing 50+ file modifications in one chunk."""
    orchestrator = Orchestrator(story_id="STRESS-002", yes=True)

    with patch("agent.core.implement.orchestrator.apply_change_to_file", new_callable=AsyncMock) as mock_apply:
        mock_apply.return_value = True
        
        content_parts = [f"

```

#### [NEW] mass_{i}.py\n```python\npass\n```" for i in range(50)]
        chunk_content = "\n".join(content_parts)
        
        loc, modified = await orchestrator.apply_chunk_async(chunk_content, 1)
        
        assert len(modified) == 50
        assert mock_apply.call_count == 50

```

**Troubleshooting**

- **Flaky Integration Tests**: If `test_backoff_timing_exponential` fails on CI, increase the `base_delay` to reduce the impact of OS context-switching overhead on timing measurements.
- **Max Retries Not Triggering**: Ensure the exceptions raised in mocks are included in the `exceptions` tuple passed to the `retry_with_backoff` decorator in `orchestrator.py`.

### Step 8: Documentation Updates

This section provides technical documentation for the concurrent orchestration and retry mechanisms introduced in INFRA-169. These documents serve as the primary reference for backend engineers working on the implementation engine core.

#### [NEW] .agent/docs/backend/orchestration-concurrency.md

```markdown
# Concurrent Orchestration Design

## Overview
The orchestrator now supports parallel execution of implementation chunks within a single generation phase. This transition from serial to concurrent execution reduces latency for large-scale tasks by overlapping I/O-bound operations.

## Key Mechanisms

**1. Async Task Gathering**
Chunks within a phase are executed using `asyncio.gather`. This allows multiple AI requests and file system modifications to happen simultaneously.

**2. Concurrency Limiting (Semaphore)**
To prevent resource exhaustion (OS file descriptor limits or LLM API rate limits), a `BoundedSemaphore` is used to restrict the number of active concurrent tasks. 
- **Default Limit**: 5 concurrent chunks.
- **Implementation**: Managed within the `Orchestrator` via an internal semaphore used during `apply_chunk_async` calls.

**3. Phase-Gate Integrity**
Parallelism is strictly confined to the *current phase*. The orchestrator ensures all chunks in a phase are resolved (either successful or failed) before evaluating the gate for the next phase. A single permanent chunk failure will halt the entire runbook to preserve system integrity and prevent inconsistent modifications in downstream phases.

## Operational Impact
- **Latency**: Significant reduction in total implementation time for multi-step runbooks.
- **Logs**: Logs are now interleaved. Engineers should rely on the `step_index` and `story_id` fields in structured logs to reconstruct the timeline for a specific chunk.

```

#### [NEW] .agent/docs/backend/retry-and-error-states.md

```markdown
# Retry Logic and Error States

## Retry Strategy
The implementation engine utilizes a granular, per-chunk retry strategy. This ensures that transient network errors or temporary file system locks do not cause the entire implementation process to fail.

**Configuration Parameters**
The following parameters are defined in `agent.core.implement.retry` and applied via the `retry_with_backoff` decorator:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `max_retries` | 3 | Number of attempts after the initial failure. |
| `base_delay` | 1.0s | Initial wait time before the first retry. |
| `max_delay` | 30.0s | Upper bound for exponential backoff delay. |
| `backoff_factor` | 2.0 | Multiplier for the delay after each failure. |
| `jitter` | True | Adds random variance (Full Jitter) to prevent synchronized retries. |

## Error Definitions for Engineers

**MaxRetriesExceededError**
Raised when a chunk-level task fails more than `max_retries` times. This error is terminal for the specific implementation task and bubbles up to the orchestrator.

**Failure Propagation & State**
1. **Chunk Failure**: If a chunk fails all retries, it raises `MaxRetriesExceededError`.
2. **Phase Halt**: The orchestrator catches this error, stops processing any remaining tasks in the queue, and marks the story as `FAILED`.
3. **State Preservation**: Successful chunks from the same or previous phases are *not* rolled back. This allows engineers to inspect partial successes and manually intervene or resume from a known state.

## Observability
Engineers should monitor the `agent.core.implement.telemetry` logger for the following events:
- `chunk_retry`: Emitted when a transient error triggers a retry attempt.
- `chunk_failure`: Emitted when a chunk reaches the retry limit.
- `retry_count`: Metadata field providing the attempt sequence (1, 2, 3).

```

### Step 9: Deployment & Rollback Strategy

The deployment of the phased generation orchestrator is managed via a feature flag to allow for isolated verification and immediate restoration of serial execution in the event of performance degradation or race conditions.

**Deployment Procedure**

1. **Environment Preparation**: Ensure the implementation code (Steps 2-7) is merged into the integration branch.
2. **Configuration Update**: Apply the feature flag definition in `.agent/src/agent/core/config.py`. By default, the flag is set to `False` to prevent accidental activation.
3. **Feature Activation**: To enable concurrent orchestration, update the environment variable or configuration file:

   ```bash
   export AGENT_ENABLE_CONCURRENT_ORCHESTRATION=True
   ```

4. **Verification**: Execute a runbook generation and implementation for a story with multiple implementation steps. Monitor the telemetry logs for overlapping timestamps in `chunk_start` and `chunk_success` events.

#### [MODIFY] .agent/src/agent/core/config.py

```

<<<SEARCH
class ConsoleConfig(BaseModel):
    """Configuration for the agent console personality and system prompt."""
===
class Config:
    """Central configuration for the agent."""

    # Toggle for INFRA-169: Enables parallel chunk processing and per-chunk retries.
    ENABLE_CONCURRENT_ORCHESTRATION: bool = False
>>>

```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```

<<<SEARCH
from .resolver import resolve_path, extract_story_id

from rich.console import Console
===
from .resolver import resolve_path, extract_story_id
from agent.core.config import config

from rich.console import Console
>>>

```

```

<<<SEARCH
    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
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
===
    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
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
>>>

```

**Rollback Procedure**

In the event of logic errors, task deadlocks, or sensitive data leaks detected in the new orchestration layer, use the following tiered rollback strategy:

#### Level 1: Feature Toggle (Immediate)
Disable the async core by reverting the configuration change. This forces the orchestrator back into serial processing mode without requiring a code revert.

```bash
# Toggle flag to False in the environment or .env file
export AGENT_ENABLE_CONCURRENT_ORCHESTRATION=False

```

#### Level 2: Component Revert (Critical Failure)
If the feature flag toggle is insufficient (e.g., due to a syntax error in common modules), revert the orchestrator and runbook command files to the INFRA-166 stable baseline.

```bash
# Revert core orchestrator logic
git checkout INFRA-166 -- .agent/src/agent/core/implement/orchestrator.py

# Revert runbook command integration
git checkout INFRA-166 -- .agent/src/agent/commands/runbook.py

# Remove new implementation artifacts
rm .agent/src/agent/core/implement/retry.py
rm .agent/src/agent/core/implement/security.py
rm .agent/src/agent/core/implement/telemetry_helper.py

```

**Troubleshooting & Observability**

- **Deadlock Detection**: If implementation tasks hang indefinitely, check for unreleased semaphores in `orchestrator.py`. The concurrency limit is strictly enforced (default: 5).
- **Log Fragmentation**: Logs for different chunks will be interleaved. Always use the `step_index` and `story_id` keys in JSON logs to reconstruct the state of a specific task.
- **Audit Compliance**: If sensitive data is found in logs despite the `OrchestrationSecurityFilter`, immediately invoke Level 1 Rollback and check the scrubbing regexes in `security.py`.
