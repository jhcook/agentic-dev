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

"""Pre-apply validation gates for the implement command (INFRA-096, INFRA-100).

Provides docstring enforcement (AC-10) and safe-apply file-size guards
(AC-9) that run before any file is written to disk.
"""

import difflib
import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from opentelemetry import metrics
from rich.console import Console
from rich.syntax import Syntax

logger = logging.getLogger(__name__)

meter = metrics.get_meter("agent.guardrails")

intervention_counter = meter.create_counter(
    "guardrail_interventions_total",
    description="Total number of tool execution loops aborted by guardrails",
)

class ExecutionGuardrail:
    """
    Monitors tool execution for infinite loops and iteration limits.

    Attributes:
        max_iterations: Maximum number of tool calls allowed in a session.
        excluded_tools: Tools exempt from loop detection.
        iteration_count: Current number of tool calls made.
        call_history: Set of hashes representing (tool_name, parameters).
    """

    def __init__(self, max_iterations: int = 10, excluded_tools: Optional[List[str]] = None):
        """
        Initializes the guardrail state.

        Args:
            max_iterations: Max allowed tool calls before forced termination.
            excluded_tools: Tools exempt from loop detection.
        """
        self.max_iterations: int = max_iterations
        self.excluded_tools: List[str] = excluded_tools or []
        self.iteration_count: int = 0
        self.call_history: Set[str] = set()

    def _generate_call_hash(self, tool_name: str, params: Union[Dict[str, Any], str]) -> str:
        """
        Generate a deterministic hash for a tool call.

        Args:
            tool_name: Name of the tool being called.
            params: Parameters passed to the tool.

        Returns:
            A SHA-256 hash string.
        """
        # Sort keys to ensure deterministic hashing of parameters
        if isinstance(params, dict):
            param_str = json.dumps(params, sort_keys=True)
        else:
            param_str = str(params)
        payload = f"{tool_name}:{param_str}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def check_and_record(self, tool_name: str, params: Union[Dict[str, Any], str]) -> Tuple[bool, Optional[str]]:

        """
        Checks if the current call violates guardrails.

        Args:
            tool_name: Name of the tool.
            params: Tool arguments.

        Returns:
            Tuple of (is_aborted, reason).
        """
        self.iteration_count += 1

        # 1. Check iteration limit
        if self.iteration_count > self.max_iterations:
            reason = f"Maximum iteration limit ({self.max_iterations}) reached."
            intervention_counter.add(1, {"reason": "max_iterations"})
            logger.warning("Guardrail aborted execution", extra={"iteration_count": self.iteration_count, "termination_reason": "max_iterations"})
            return True, reason

        # 2. Check for redundant loops (identical tool + params)
        call_hash = self._generate_call_hash(tool_name, params)

        if tool_name not in self.excluded_tools and call_hash in self.call_history:
            reason = f"Detected recursive loop: {tool_name} called repeatedly with identical parameters."
            intervention_counter.add(1, {"reason": "repeated_call"})
            logger.warning("Guardrail aborted execution", extra={"iteration_count": self.iteration_count, "termination_reason": "repeated_call"})
            return True, reason

        self.call_history.add(call_hash)
        logger.debug("Guardrail check passed", extra={"iteration_count": self.iteration_count})
        return False, None


try:
    from opentelemetry import trace as _otel_trace
    _tracer = _otel_trace.get_tracer(__name__)
except ImportError:
    import contextlib

    class _NoOpSpan:
        """Minimal no-op span compatible with OTel Span interface."""
        def set_attribute(self, key: str, value: object) -> None:  # noqa: D401
            """No-op."""
        def __enter__(self) -> "_NoOpSpan":
            return self
        def __exit__(self, *_: object) -> None:
            pass

    class _NoOpTracer:
        """Minimal no-op tracer used when opentelemetry is not installed."""
        def start_as_current_span(self, name: str, **_: object) -> _NoOpSpan:  # noqa: D401
            """Return a no-op span context manager."""
            return _NoOpSpan()

    _tracer: Any = _NoOpTracer()

# ---------------------------------------------------------------------------
# Thresholds (INFRA-096)
# ---------------------------------------------------------------------------

FILE_SIZE_GUARD_THRESHOLD: int = 500
SOURCE_CONTEXT_MAX_LOC: int = 300
SOURCE_CONTEXT_HEAD_TAIL: int = 100

class ImplementGuardViolation(Exception):
    """Base class for all implementation guard violations."""
    pass

class FileSizeGuardViolation(ImplementGuardViolation):
    """Raised when a file change violates the size safety threshold."""
    pass

class DocstringGuardViolation(ImplementGuardViolation):
    """Raised when a file change lacks required PEP-257 docstrings."""
    pass

_console = Console()


# ---------------------------------------------------------------------------
# Code Validation Gates (INFRA-155)
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Container for code validation findings."""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if no errors are present."""
        return not bool(self.errors)

def validate_code_block(filepath: str, content: str) -> ValidationResult:
    """Run all code-level gates against a proposed code block.

    Uses ``start_as_current_span`` so child spans from sub-validators are
    correctly nested as children of this span in the trace hierarchy (INFRA-155).
    """
    with _tracer.start_as_current_span("guards.validate_code_block") as span:
        span.set_attribute("file", filepath)

        result = ValidationResult()

        # AC-1: Trailing newline normalisation — auto-correct rather than block.
        # The AI panel routinely omits the final \n; treating it as a hard error
        # burns retry budget on a trivial mechanical issue. Auto-correct and warn.
        if content and not content.endswith("\n"):
            content = content + "\n"
            result.warnings.append(f"{filepath}: missing trailing newline (auto-corrected)")

        # Python-specific checks
        if filepath.endswith(".py"):
            doc_res = enforce_docstrings(filepath, content)
            result.errors.extend(doc_res.errors)
            result.warnings.extend(doc_res.warnings)

            import_res = check_imports(filepath, content)
            result.errors.extend(import_res.errors)

        span.set_attribute("validation.passed", result.passed)
        span.set_attribute("validation.error_count", len(result.errors))
    return result

def enforce_docstrings(filepath: str, content: str) -> ValidationResult:  # noqa: C901
    """Check generated Python source for missing PEP-257 docstrings.

    Uses ``start_as_current_span`` so this span appears as a child of
    ``validate_code_block`` in the trace hierarchy (INFRA-155).
    """
    import ast

    with _tracer.start_as_current_span("guards.enforce_docstrings") as span:
        span.set_attribute("file", filepath)

        result = ValidationResult()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return result

        filename = Path(filepath).name

        def _has_docstring(node: ast.AST) -> bool:
            """Return True if node's first body statement is a string literal."""
            return (
                bool(getattr(node, "body", None))
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )

        if not _has_docstring(tree):
            result.errors.append(f"{filename}: module is missing a docstring")

        # Union type used so the helper handles both FunctionDef and AsyncFunctionDef
        # without requiring a type: ignore suppression.
        _FuncNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]

        class DocstringVisitor(ast.NodeVisitor):
            """AST visitor to find missing docstrings at different nesting levels."""

            context_stack: List[ast.AST]  # Stack of scope nodes (ClassDef, FunctionDef…)

            def __init__(self) -> None:
                self.context_stack = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                """Visit class and check for a class-level docstring."""
                if not _has_docstring(node):
                    result.errors.append(f"{filename}: class {node.name} is missing a docstring")
                self.context_stack.append(node)
                self.generic_visit(node)
                self.context_stack.pop()

            def _check_func_node(self, node: "_FuncNode") -> None:
                """Shared docstring check for FunctionDef and AsyncFunctionDef."""
                if not _has_docstring(node):
                    is_nested = any(
                        isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef))
                        for p in self.context_stack
                    )
                    if is_nested:
                        result.warnings.append(
                            f"{filename}: nested function {node.name}() is missing a docstring"
                        )
                    else:
                        result.errors.append(f"{filename}: {node.name}() is missing a docstring")
                self.context_stack.append(node)
                self.generic_visit(node)
                self.context_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                """Delegate to shared function-node checker."""
                self._check_func_node(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                """Delegate async function to shared function-node checker."""
                self._check_func_node(node)

        DocstringVisitor().visit(tree)
        span.set_attribute("validation.passed", result.passed)
        span.set_attribute("validation.error_count", len(result.errors))
    return result

def check_impact_analysis_completeness(runbook_content: str) -> List[str]:
    """Verify that every modified file is listed in the Step N summary.

    Checks files mentioned in [MODIFY], [NEW], and [DELETE] blocks against
    the 'Components touched:' section in the Impact Analysis update step.

    Args:
        runbook_content: The full content of the generated runbook.

    Returns:
        List of error messages for missing documentation.
    """
    import re
    from pathlib import Path

    with _tracer.start_as_current_span("guards.check_impact_analysis") as span:
        # 1. Extract files from runbook headers
        # Exclude CHANGELOG.md and story files as they are standard housekeeping
        ops = re.findall(r"####\s*\[(?:MODIFY|NEW|DELETE)\]\s*([^ \n`]+)", runbook_content)
        touched_files = {
            Path(f).as_posix() for f in ops
            if not f.endswith("CHANGELOG.md") and ".agent/cache/stories/" not in f
        }

        # 2. Extract files from the "Components touched:" list in Step N
        # We look for the block intended to be written to the story file
        summary_match = re.search(
            r"\*\*Components touched:\*\*\s*\n((?:\s*-\s*`[^`]+`[^\n]*\n?)+)",
            runbook_content,
            re.MULTILINE
        )

        documented_files: Set[str] = set()
        if summary_match:
            lines = summary_match.group(1).splitlines()
            for line in lines:
                file_match = re.search(r"-\s*`([^`]+)`", line)
                if file_match:
                    documented_files.add(Path(file_match.group(1)).as_posix())

        missing = touched_files - documented_files
        span.set_attribute("files_touched", len(touched_files))
        span.set_attribute("files_documented", len(documented_files))
        span.set_attribute("missing_count", len(missing))

        if not missing:
            return []

        return [
            f"Impact Analysis Gap: `{f}` is modified/created in implementation steps but missing from the Step N Impact Analysis summary"
            for f in sorted(missing)
        ]


def check_adr_refs(runbook_content: str, adr_dir: Path) -> List[str]:
    """Validate that all ADR-NNN citations exist in the catalogue.

    Args:
        runbook_content: The full content of the generated runbook.
        adr_dir: Path to the directory containing ADR markdown files.

    Returns:
        List of error messages for hallucinated ADR references.
    """
    import re

    with _tracer.start_as_current_span("guards.check_adr_refs") as span:
        # Extract all ADR-NNN patterns
        refs = set(re.findall(r"ADR-\d+", runbook_content))
        if not refs:
            return []

        if not adr_dir.exists():
            span.set_attribute("error", "adr_dir_missing")
            return [f"ADR directory not found at {adr_dir}"]

        # Map existing ADR IDs to filenames
        existing_ids: Set[str] = set()
        for adr_file in adr_dir.glob("ADR-*.md"):
            match = re.match(r"(ADR-\d+)", adr_file.name)
            if match:
                existing_ids.add(match.group(1))

        invalid = refs - existing_ids
        span.set_attribute("refs_found", len(refs))
        span.set_attribute("invalid_count", len(invalid))

        if not invalid:
            return []

        return [
            f"Hallucinated ADR: `{adr}` is cited but does not exist in the on-disk catalogue"
            for adr in sorted(invalid)
        ]


def check_op_type_vs_filesystem(runbook_content: str, repo_root: Path) -> List[str]:
    """Verify that [MODIFY] and [DELETE] operations target files that exist on disk.

    Catches AI-generated runbooks that use [MODIFY] on files that do not yet
    exist (which should be [NEW]) before they reach the apply-time
    ``sr_modify_missing`` autohealer. This prevents free-pass conversions from
    consuming retry budget and surfaces the mismatch as an actionable gate error.

    Args:
        runbook_content: The full content of the generated runbook.
        repo_root: Absolute path to the repository root used to resolve
            repo-relative file paths from the runbook headers.

    Returns:
        List of error messages for each mismatched operation.
    """
    import re as _re

    with _tracer.start_as_current_span("guards.check_op_type_vs_filesystem") as span:
        _EXEMPT_SUFFIXES = ("CHANGELOG.md",)
        _EXEMPT_PREFIXES = (".agent/cache/",)

        ops = _re.findall(
            r"####\s*\[(MODIFY|DELETE)\]\s*([^ \n`]+)",
            runbook_content,
        )

        errors: List[str] = []
        checked = 0
        for op, raw_path in ops:
            path = raw_path.strip()
            if any(path.endswith(s) for s in _EXEMPT_SUFFIXES):
                continue
            if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
                continue
            resolved = repo_root / path
            if not resolved.exists():
                errors.append(
                    f"Op-type mismatch: `{path}` uses [{op}] but the file does not "
                    f"exist on disk — change to [NEW] and provide a full code block."
                )
            checked += 1

        span.set_attribute("paths_checked", checked)
        span.set_attribute("mismatch_count", len(errors))
        return errors



def check_stub_implementations(runbook_content: str) -> List[str]:
    """Detect placeholder / stub implementations in AI-generated code blocks.

    Catches patterns that indicate the AI left an incomplete implementation:
    - ``pass`` as the sole statement in a function or method body
    - ``raise NotImplementedError``
    - ``# TODO``, ``# FIXME``, ``# HACK`` comments
    - Common stub phrases: "implementation here", "logic here",
      "orchestrate … here", "…goes here", "left as an exercise", etc.

    Only inspects the *content* of fenced code blocks inside the runbook
    (i.e. what will actually be written to disk) — not prose sections.

    Returns:
        List of descriptive error strings, one per stub pattern found.
    """
    import re as _re

    with _tracer.start_as_current_span("guards.check_stub_implementations") as span:
        # Extract fenced code blocks (``` … ```)
        code_blocks = _re.findall(r"```(?:[a-z]*)?\n(.*?)```", runbook_content, _re.DOTALL)

        # Patterns that indicate an incomplete implementation
        _STUB_PATTERNS: List[tuple] = [
            (_re.compile(r"^\s*pass\s*$", _re.MULTILINE), "bare `pass` statement"),
            (_re.compile(r"raise\s+NotImplementedError", _re.IGNORECASE), "`raise NotImplementedError`"),
            (_re.compile(r"#\s*(TODO|FIXME|HACK)\b", _re.IGNORECASE), "TODO/FIXME/HACK comment"),
            (
                _re.compile(
                    r"#.*(?:implementation|logic|orchestrat|goes here|left as an exercise|add here|insert here)",
                    _re.IGNORECASE,
                ),
                "stub comment placeholder",
            ),
            (_re.compile(r"\.{3}\s*#", _re.IGNORECASE), "ellipsis stub (``...  #``)"),
        ]

        errors: List[str] = []
        for block in code_blocks:
            for pattern, label in _STUB_PATTERNS:
                if pattern.search(block):
                    # Surface a one-sentence error per unique label to keep the
                    # correction prompt concise.
                    msg = (
                        f"Stub detected ({label}) — the code block contains an incomplete "
                        f"implementation. Replace every placeholder with a real, working "
                        f"implementation before submitting the runbook."
                    )
                    if msg not in errors:
                        errors.append(msg)

        span.set_attribute("blocks_checked", len(code_blocks))
        span.set_attribute("stub_count", len(errors))
        return errors


def check_imports(filepath: str, content: str) -> ValidationResult:

    """Validate imports against project dependencies.

    Uses ``start_as_current_span`` so this span appears as a child of
    ``validate_code_block`` in the trace hierarchy (INFRA-155).
    """
    import ast
    import re as _re
    import sys
    from agent.core.config import resolve_repo_path

    with _tracer.start_as_current_span("guards.check_imports") as span:
        span.set_attribute("file", filepath)

        result = ValidationResult()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return result

        # 1. Gather allowed packages
        allowed: Set[str] = {"agent", "tests", "backend", "web"}  # local project roots

        # Test files legitimately import pytest, typer (for CLI invocation), and
        # other test-only packages that may not appear in the production dep list.
        _test_only: Set[str] = {
            "pytest", "pytest_asyncio", "typer", "click", "unittest",
            "mock", "fakeredis", "httpx", "respx", "freezegun",
        }
        _is_test_file = (
            Path(filepath).name.startswith("test_")
            or Path(filepath).name.endswith("_test.py")
            or "/tests/" in filepath.replace("\\", "/")
        )
        if _is_test_file:
            allowed.update(_test_only)

        # Add standard library
        if sys.version_info >= (3, 10):
            allowed.update(sys.stdlib_module_names)

        # Add dependencies from pyproject.toml using robust TOML parsing (no fragile regex)
        # Try multiple candidate locations: repo root first, then .agent/ subdirectory.
        _pyproject_candidates = [
            resolve_repo_path("pyproject.toml"),
            resolve_repo_path(".agent/pyproject.toml"),
        ]
        pyproject_path = next((p for p in _pyproject_candidates if p.exists()), None)
        if pyproject_path:
            try:
                try:
                    import tomllib  # Python 3.11+
                except ImportError:
                    import tomli as tomllib  # type: ignore[no-redef]  # backport
                with pyproject_path.open("rb") as fh:
                    toml_data = tomllib.load(fh)
                raw_deps: List[str] = toml_data.get("project", {}).get("dependencies", [])
                for section in toml_data.get("project", {}).get("optional-dependencies", {}).values():
                    raw_deps.extend(section)
                raw_deps.extend(
                    toml_data.get("tool", {}).get("uv", {}).get("dev-dependencies", [])
                )
                for dep in raw_deps:
                    # Strip extras (e.g. pkg[extra] -> pkg)
                    base_dep = _re.split(r'[;\[>=<]', str(dep))[0].strip()
                    m = _re.match(r'^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)', base_dep)
                    if m:
                        pkg_name = m.group(1)
                        # Normalise hyphens/dots to underscores (PEP 503)
                        normalised = pkg_name.replace("-", "_").replace(".", "_").lower()
                        allowed.add(normalised)
                        
                        # Handle known hyphenated namespace mappings
                        # e.g. opentelemetry-api -> opentelemetry
                        if "-" in pkg_name:
                            top_level = pkg_name.split("-")[0].lower()
                            allowed.add(top_level)
            except Exception as exc:
                logger.warning("Failed to parse pyproject.toml for dependency check: %s", exc)

        # 2. Check imports in the tree
        for node in ast.walk(tree):
            module_name = ""
            is_relative = False
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                is_relative = (node.level or 0) > 0
                if node.module:
                    module_name = node.module.split(".")[0]

            if module_name and not is_relative and module_name not in allowed:
                result.errors.append(f"{filepath}: undeclared dependency '{module_name}' imported")

        span.set_attribute("validation.passed", result.passed)
        span.set_attribute("validation.error_count", len(result.errors))
    return result


# ---------------------------------------------------------------------------
# File backup
# ---------------------------------------------------------------------------


def backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup of a file before modification.

    Args:
        file_path: Path to the file to back up.

    Returns:
        Path to the backup file, or None if the source does not exist.
    """
    if not file_path.exists():
        return None
    from agent.core.config import resolve_repo_path
    backup_dir = resolve_repo_path(".agent/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{file_path.name}.backup-{timestamp}"
    shutil.copy2(file_path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------


def _fuzzy_find_and_replace(
    content: str,
    search: str,
    replace: str,
    filepath: str,
    block_num: int,
    total_blocks: int,
    threshold: float = 0.6,
) -> Optional[str]:
    """Find the best fuzzy match for search text in content and apply replacement.

    Uses a sliding window of lines sized to the search block to find the
    highest-similarity contiguous region.  If similarity >= threshold,
    replaces that region with the replace text.

    Args:
        content: The full file content to search in.
        search: The search text to match (may not match exactly).
        replace: The replacement text.
        filepath: File path for logging.
        block_num: Block number for logging.
        total_blocks: Total blocks for logging.
        threshold: Minimum similarity ratio (0.0–1.0).

    Returns:
        The modified content if a fuzzy match was applied, None otherwise.
    """
    search_lines = search.splitlines(keepends=True)
    content_lines = content.splitlines(keepends=True)
    window_size = len(search_lines)

    if window_size == 0 or len(content_lines) == 0:
        return None

    best_ratio = 0.0
    best_start = -1

    # Slide window across all possible positions
    for start in range(max(1, len(content_lines) - window_size + 1)):
        end = min(start + window_size, len(content_lines))
        candidate = content_lines[start:end]
        ratio = difflib.SequenceMatcher(
            None, "".join(candidate), search
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = start

    if best_ratio >= threshold and best_start >= 0:
        best_end = min(best_start + window_size, len(content_lines))
        matched_text = "".join(content_lines[best_start:best_end])
        _console.print(
            f"[yellow]🔍 Fuzzy matched block {block_num}/{total_blocks} in {filepath} "
            f"(similarity: {best_ratio:.0%})[/yellow]"
        )
        logging.info(
            "search_replace_fuzzy_match file=%s block=%d/%d similarity=%.2f",
            filepath, block_num, total_blocks, best_ratio,
        )
        return content.replace(matched_text, replace, 1)

    logging.warning(
        "search_replace_fuzzy_no_match file=%s block=%d/%d best_ratio=%.2f threshold=%.2f",
        filepath, block_num, total_blocks, best_ratio, threshold,
    )
    return None


def apply_search_replace_to_file(
    filepath: str,
    blocks: List[Dict[str, str]],
    yes: bool = False,
) -> tuple[bool, str]:
    """Apply search/replace blocks surgically to an existing file.

    All blocks are verified (dry-run) before any change is written.
    If any block fails to match, the entire operation is aborted.

    Args:
        filepath: Repo-relative file path.
        blocks: List of dicts with 'search' and 'replace' keys.
        yes: Skip confirmation prompts.

    Returns:
        Tuple of (success, final_content). On failure, final_content is
        the original unchanged content.
    """
    
    from agent.core.implement.orchestrator import resolve_path  # avoid circular at module level
    from agent.core.config import resolve_repo_path
    import typer

    span_ctx = None
    if _tracer:
        span_ctx = _tracer.start_span("implement.apply_change")
        span_ctx.set_attribute("file", filepath)
        span_ctx.set_attribute("apply_mode", "search_replace")

    resolved_path = resolve_path(filepath)
    if not resolved_path or not resolved_path.exists():
        _console.print(
            f"[bold red]❌ Cannot apply search/replace to '{filepath}': file not found.[/bold red]"
        )
        return False, ""

    original_content = resolved_path.read_text()
    working_content = original_content

    for i, block in enumerate(blocks):
        if block["search"] in working_content:
            match_count = working_content.count(block["search"])
            if match_count > 1:
                logging.warning(
                    "search_replace_ambiguous file=%s block=%d match_count=%d",
                    filepath, i + 1, match_count,
                )
            working_content = working_content.replace(block["search"], block["replace"], 1)
        else:
            # Fuzzy match fallback: find best matching region
            _fuzzy_result = _fuzzy_find_and_replace(
                working_content, block["search"], block["replace"], filepath, i + 1, len(blocks)
            )
            if _fuzzy_result is not None:
                working_content = _fuzzy_result
            else:
                _console.print(
                    f"[bold red]❌ Search block {i+1}/{len(blocks)} not found in {filepath}.[/bold red]"
                )
                logging.warning(
                    "search_replace_match_failure file=%s block=%d/%d",
                    filepath, i + 1, len(blocks),
                )
                if span_ctx:
                    span_ctx.end()
                return False, original_content

    _console.print(f"\n[bold cyan]📝 Search/Replace for: {filepath}[/bold cyan]")
    diff_lines = list(difflib.unified_diff(
        original_content.splitlines(keepends=True),
        working_content.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    ))
    if diff_lines:
        _console.print(Syntax("".join(diff_lines), "diff", theme="monokai"))

    if not yes:
        import typer as _typer
        if not _typer.confirm(f"\nApply {len(blocks)} block(s) to {filepath}?", default=False):
            _console.print("[yellow]⏭️  Skipped[/yellow]")
            if span_ctx:
                span_ctx.end()
            return False, original_content

    backup_path = backup_file(resolved_path)
    if backup_path:
        _console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")

    try:
        resolved_path.write_text(working_content)
        _console.print(f"[bold green]✅ Applied {len(blocks)} block(s) to {filepath}[/bold green]")
        logging.info(
            "apply_change apply_mode=search_replace file=%s blocks=%d",
            filepath, len(blocks),
        )
        log_file = resolve_repo_path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] SearchReplace: {filepath} ({len(blocks)} blocks)\n")
        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True, working_content
    except Exception as exc:
        _console.print(f"[bold red]❌ Failed to write file: {exc}[/bold red]")
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False, original_content


def apply_change_to_file(
    filepath: str,
    content: str,
    yes: bool = False,
    legacy_apply: bool = False,
) -> bool:
    """Apply code changes to a file with smart path resolution and size guard.

    For existing files exceeding FILE_SIZE_GUARD_THRESHOLD, rejects full-file
    overwrites unless legacy_apply is True (AC-5 backward compat).

    Args:
        filepath: Repo-relative file path.
        content: New file content.
        yes: Skip confirmation prompts.
        legacy_apply: Bypass safe-apply guard (audit-logged).

    Returns:
        True if the file was written successfully, False otherwise.
    """
    from agent.core.implement.orchestrator import resolve_path
    from agent.core.config import resolve_repo_path

    span_ctx = None
    if _tracer:
        span_ctx = _tracer.start_span("implement.apply_change")
        span_ctx.set_attribute("file", filepath)
        span_ctx.set_attribute("apply_mode", "full_file")

    resolved_path = resolve_path(filepath)
    if not resolved_path:
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False

    file_path = resolved_path
    filepath = str(resolved_path)

    if file_path.exists() and not legacy_apply:
        try:
            existing_lines = len(file_path.read_text().splitlines())
        except Exception:
            existing_lines = 0
        if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
            if span_ctx:
                span_ctx.set_attribute("success", False)
                span_ctx.end()
            raise FileSizeGuardViolation(
                f"File '{filepath}' already exists and new content is {existing_lines} lines. "
                f"Maximum allowed for full-file replace is {FILE_SIZE_GUARD_THRESHOLD} LOC. "
                "Hint: Update runbook step to use <<<SEARCH/===/>>> blocks for incremental changes, "
                "or pass --legacy-apply to bypass."
            )

    _console.print(f"\n[bold cyan]📝 Changes for: {filepath}[/bold cyan]")
    if file_path.exists():
        _console.print("[yellow]File exists. Showing new content:[/yellow]")
    else:
        _console.print("[green]New file will be created.[/green]")
    _console.print(Syntax(
        content,
        "python" if filepath.endswith(".py") else "text",
        theme="monokai", line_numbers=True,
    ))

    if not yes:
        import typer as _typer
        if not _typer.confirm(f"\nApply changes to {filepath}?", default=False):
            _console.print("[yellow]⏭️  Skipped[/yellow]")
            if span_ctx:
                span_ctx.end()
            return False

    if file_path.exists():
        bp = backup_file(file_path)
        if bp:
            _console.print(f"[dim]💾 Backup created: {bp}[/dim]")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file_path.write_text(content)
        _console.print(f"[bold green]✅ Applied changes to {filepath}[/bold green]")
        from agent.commands.license import apply_license_to_file
        if apply_license_to_file(file_path):
            _console.print(f"[dim]Added copyright header to {filepath}[/dim]")
        logging.info(
            "apply_change apply_mode=full_file file=%s lines_changed=%d",
            filepath, len(content.splitlines()),
        )
        log_file = resolve_repo_path(".agent/logs/implement_changes.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Modified: {filepath}\n")
        if span_ctx:
            span_ctx.set_attribute("success", True)
            span_ctx.end()
        return True
    except Exception as exc:
        _console.print(f"[bold red]❌ Failed to write file: {exc}[/bold red]")
        if span_ctx:
            span_ctx.set_attribute("success", False)
            span_ctx.end()
        return False

def autocorrect_runbook_fences(content: str) -> tuple:
    """Auto-correct common fence issues in generated runbooks.

    Fixes:
    - Missing blank lines before/after code fences
    - Unbalanced fences

    Args:
        content: Raw runbook markdown.

    Returns:
        Tuple of (corrected_content, list_of_corrections).
    """
    import re as _re
    corrections = []

    # Fix: ensure blank line before opening fence
    fixed = _re.sub(r'([^\n])\n(```)', r'\1\n\n\2', content)
    if fixed != content:
        corrections.append("Added blank lines before code fences")
        content = fixed

    # Fix: ensure blank line after closing fence
    fixed = _re.sub(r'(```)\n([^\n])', r'\1\n\n\2', content)
    if fixed != content:
        corrections.append("Added blank lines after code fences")
        content = fixed

    return content, corrections


def lint_runbook_syntax(content: str) -> list:
    """Check runbook for common syntax issues.

    Args:
        content: Runbook markdown content.

    Returns:
        List of error strings. Empty if no issues found.
    """
    import re as _re
    errors = []

    # Check for balanced fences
    fence_count = len(_re.findall(r'^```', content, _re.MULTILINE))
    if fence_count % 2 != 0:
        errors.append(f"Unbalanced code fences: {fence_count} fence markers (expected even)")

    # Check for __name__ rendered as **name**
    if '**name**' in content or '**main**' in content:
        errors.append("Detected markdown-corrupted Python dunder: **name** or **main** (should be __name__ or __main__)")

    return errors
