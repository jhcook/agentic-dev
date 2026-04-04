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

"""Chunked runbook generation pipeline.

Extracted from ``runbook.py`` to keep module LOC under the quality gate.
Contains the two-phase skeleton+block generation pipeline and the
auto-fencing helper for [NEW] blocks.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.logger import get_logger
import asyncio
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt
from agent.core.engine.executor import TaskExecutor

try:
    from observability.token_counter import UsageTracker, get_token_count as _token_count
except ImportError:  # pragma: no cover
    UsageTracker = None  # type: ignore[assignment,misc]
    _token_count = lambda text, **_: len(text) // 4  # noqa: E731


# ---------------------------------------------------------------------------
# Generation-domain models (distinct from parser-domain in chunk_models.py)
# ---------------------------------------------------------------------------


@dataclass
class GenerationSection:
    """A section in the AI-generated skeleton (table-of-contents entry)."""

    title: str
    description: str = ""
    files: List[str] = field(default_factory=list)


@dataclass
class GenerationSkeleton:
    """AI-generated skeleton: title + ordered list of sections."""

    title: str
    sections: List[GenerationSection]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationSkeleton":
        """Build from the JSON dict returned by the AI."""
        sections = [
            GenerationSection(
                title=s.get("title", f"Section {i+1}"),
                description=s.get("description", ""),
                files=s.get("files", []),
            )
            for i, s in enumerate(data.get("sections", []))
        ]
        return cls(title=data.get("title", "Untitled Runbook"), sections=sections)


@dataclass
class GenerationBlock:
    """A single generated implementation block from Phase 2."""

    header: str
    content: str = ""
    ops: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationBlock":
        """Build from the JSON dict returned by the AI.

        Supports both the legacy ``content`` format and the new structured
        ``ops`` format introduced by INFRA-181.
        """
        header = data.get("header", data.get("title", "Untitled"))
        ops = data.get("ops", [])
        if ops and isinstance(ops, list):
            return cls(header=header, ops=_sanitize_json_values(ops))
        return cls(
            header=header,
            content=data.get("content", data.get("body", "")),
        )


def _is_verification_section(section: GenerationSection) -> bool:
    """Check if a section is a verification/test block based on heuristics."""
    v_patterns = ("test", "verify", "verification", "validate", "qa", "suite", "check")
    title_match = any(p in section.title.lower() for p in v_patterns)
    file_match = any("tests/" in f.lower() or "test_" in f.lower() or "_test" in f.lower() for f in section.files)
    return title_match or file_match


logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()
error_console = Console(stderr=True)


def _extract_json(raw: str) -> Dict[str, Any]:
    """Robustly extract a JSON object from AI output."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        # Remove opening fence (```json, ```, etc.)
        text = re.sub(r'^```\w*\n?', '', text, count=1)
        # Remove closing fence
        text = re.sub(r'\n?```\s*$', '', text)
        text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Balanced-brace extraction: find the top-level JSON object
    # by counting braces instead of greedy regex
    start = text.find('{')
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Try the next opening brace
                        next_start = text.find('{', start + 1)
                        if next_start != -1:
                            start = next_start
                            depth = 0
                            continue
                        break

    # Final fallback: raise with the original text for debugging
    return json.loads(text)  # Will raise JSONDecodeError




def _sanitize_json_values(data: Any) -> Any:
    """Recursively strip spurious markdown fences from LLM-generated JSON values.

    The LLM sometimes wraps ``content``, ``search``, or ``replace`` values in
    triple-backtick fences even when instructed not to.  This pass removes them
    from every string value in the ops list so the assembler receives raw code.
    """
    if isinstance(data, dict):
        return {k: _sanitize_json_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_json_values(item) for item in data]
    if isinstance(data, str):
        s = data.strip()
        # Strip a leading code fence (```python, ```, ~~~, etc.)
        s = re.sub(r'^(?:```|~~~)\w*\n?', '', s)
        # Strip a trailing code fence
        s = re.sub(r'\n?(?:```|~~~)\s*$', '', s)
        return s
    return data


def _assemble_block_from_json(block: "GenerationBlock") -> str:
    """Convert structured JSON ops into markdown with injected delimiters.

    This is the core of INFRA-181: the LLM never writes ``<<<SEARCH``,
    ``===``, ``>>>``, or ``#### [NEW/MODIFY/DELETE]`` — Python does.
    If the block has no ops (legacy ``content`` field), returns content as-is.
    """
    if not block.ops:
        return block.content

    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }

    parts: List[str] = []
    for op in block.ops:
        action = str(op.get("op", "modify")).upper()
        path = op.get("file", "unknown")
        parts.append(f"#### [{action}] {path}")
        parts.append("")  # blank line after header

        if action == "NEW":
            content = op.get("content", "")
            # Infer language from file extension for syntax highlighting
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            lang = ext_lang.get(ext, "")
            parts.append(f"```{lang}")
            parts.append(content)
            parts.append("```")

        elif action == "MODIFY":
            search = op.get("search", "")
            replace = op.get("replace", "")
            parts.append("```")
            parts.append("<<<SEARCH")
            parts.append(search)
            parts.append("===")
            parts.append(replace)
            parts.append(">>>")
            parts.append("```")

        elif action == "DELETE":
            rationale = op.get("rationale", "File no longer needed.")
            parts.append(f"Rationale: {rationale}")

        parts.append("")  # blank line between ops

    return "\n".join(parts).strip()


def _ensure_new_blocks_fenced(content: str) -> str:
    """Wrap unfenced [NEW] block content in code fences.

    Scans for ``#### [NEW] <path>`` headers and checks if the content
    between that header and the next ``####`` / ``###`` header is fenced.
    If not, wraps it in a fenced code block with language inferred from
    the file extension.

    Always uses backtick fences (MD048). The inner content of .md files
    is written by the AI and typically does not contain triple-backtick
    code blocks — and when it does, the fence rebalancer closes any
    orphaned fences deterministically.
    """
    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }
    # Split on [NEW] headers, preserving the header
    parts = re.split(r'(####\s+\[NEW\]\s+.+)', content)
    result = []
    for idx, part in enumerate(parts):
        result.append(part)
        # Check if this is a [NEW] header and the NEXT part is content
        if re.match(r'####\s+\[NEW\]\s+', part) and idx + 1 < len(parts):
            body = parts[idx + 1]
            # Check if body already contains a code fence
            if not re.search(r'(?:^|\n)\s*(`{3,}|~{3,})', body):
                # Extract path for language detection
                path_match = re.search(r'\[NEW\]\s+(.+)', part)
                path = path_match.group(1).strip().strip('`') if path_match else ""
                ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
                lang = ext_lang.get(ext, "")
                body_stripped = body.strip('\n')
                parts[idx + 1] = f"\n```{lang}\n{body_stripped}\n```\n"
    return "".join(result)


def _normalize_list_markers(content: str) -> str:
    """Normalise bullet and ordered-list markers to satisfy MD004/MD030.

    Converts ``*   item`` (asterisk + 3 spaces) to ``- item`` (dash +
    1 space) and ``N.  item`` (2+ spaces after period) to ``N. item``
    (1 space).  Only operates on lines that are clearly list items
    (outside of fenced code blocks).
    """
    lines = content.splitlines(keepends=True)
    in_fence = False
    result = []
    for line in lines:
        # Track fence state so we don't mangle code inside blocks
        stripped = line.lstrip()
        if re.match(r'^(`{3,}|~{3,})\S*\s*$', stripped):
            in_fence = not in_fence
        if not in_fence:
            # MD004: asterisk bullet → dash
            line = re.sub(r'^(\s*)\*( {2,})', lambda m: m.group(1) + '- ', line)
            # MD030: multiple spaces after ordered-list period
            line = re.sub(r'^(\s*\d+\.)(\s{2,})', lambda m: m.group(1) + ' ', line)
        result.append(line)
    return "".join(result)


def _fix_changelog_sr_headings(content: str) -> str:
    """Rewrite CHANGELOG S/R SEARCH blocks to avoid MD024/MD025 violations.

    The AI consistently uses ``# Changelog`` as the SEARCH anchor, which
    is a top-level heading inside the runbook and triggers MD025 (multiple
    H1s) and MD024 (duplicate headings).  This pass rewrites the SEARCH
    side to use the first sub-heading inside the file (``## [Unreleased]``)
    instead, which is equally unique but doesn't violate heading rules.
    """
    # Pattern: inside a fenced block, a <<<SEARCH that anchors on # Changelog
    return re.sub(
        r'<<<SEARCH\n# Changelog\n===\n# Changelog',
        '<<<SEARCH\n## [Unreleased]\n===\n## [Unreleased] (Updated by story)',
        content,
    )


def _ensure_blank_lines_around_fences(content: str) -> str:
    """Ensure every fenced code block is surrounded by blank lines (MD031).

    Inserts a blank line before an opening fence when the previous line
    is non-empty prose, and after a closing fence when the next line is
    non-empty.  Skips fences already correctly surrounded.
    """
    # Blank line before an opening fence if immediately preceded by text
    content = re.sub(r'([^\n])\n(```|~~~)', r'\1\n\n\2', content)
    # Blank line after a closing fence if immediately followed by text
    content = re.sub(r'(^```|^~~~)(\n)([^\n`~])', r'\1\2\n\3', content, flags=re.MULTILINE)
    return content


def _rebalance_fences(content: str) -> str:
    """Deterministically close any orphaned code fences in each Step block.

    The LLM cannot reliably balance nested fences, especially when embedding
    ``.md`` files that contain their own code examples.  Rather than trusting
    the model, this pass makes fence balance a *pipeline guarantee*.

    Strategy
    --------
    1. Split the assembled runbook on ``### Step N:`` boundaries.
    2. Within each block, walk line-by-line tracking open/close state of
       *backtick* fences and *tilde* fences independently (separate
       namespaces in CommonMark).
    3. If a block ends with an open fence, append the matching closer
       (``` or ~~~) before the next step begins.

    This is purely syntactic — no AI involved.
    """
    step_pat = re.compile(r'(?=^### Step \d+:)', re.MULTILINE)
    parts = step_pat.split(content)

    fixed_parts: list = []
    total_closers_added = 0

    backtick_fence_re = re.compile(r'^\s*(`{3,})\w*\s*$')
    tilde_fence_re = re.compile(r'^\s*(~{3,})\w*\s*$')

    for part in parts:
        backtick_open = False
        tilde_open = False

        for line in part.splitlines():
            if backtick_fence_re.match(line):
                backtick_open = not backtick_open
            elif tilde_fence_re.match(line):
                tilde_open = not tilde_open

        closers = ""
        if backtick_open:
            closers += "```\n"
            total_closers_added += 1
            logger.warning(
                "fence_rebalanced",
                extra={"type": "backtick", "block_preview": part[:80].strip()},
            )
        if tilde_open:
            closers += "~~~\n"
            total_closers_added += 1
            logger.warning(
                "fence_rebalanced",
                extra={"type": "tilde", "block_preview": part[:80].strip()},
            )
        fixed_parts.append(part + closers)

    if total_closers_added:
        console.print(
            f"[yellow]🔧 Fence rebalancer: closed {total_closers_added} "
            f"orphaned fence(s)[/yellow]"
        )

    return "".join(fixed_parts)


def _ensure_modify_blocks_fenced(content: str) -> str:
    """Wrap unfenced [MODIFY] S/R block content in code fences.

    Scans for ``#### [MODIFY] <path>`` headers and checks if the body
    between that header and the next ``####`` / ``###`` header has a
    code fence enclosing the ``<<<SEARCH`` / ``===`` / ``>>>`` markers.
    If not, wraps the bare S/R content in a fenced code block with
    language inferred from the file extension.

    This autocorrects the common AI failure where the MODIFY block is
    emitted directly after the heading without a fenced code block.
    """
    ext_lang = {
        ".py": "python", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".sh": "bash", ".md": "markdown",
        ".toml": "toml", ".js": "javascript", ".ts": "typescript",
    }
    # Split on [MODIFY] headers, preserving the header line
    parts = re.split(r'(####\s+\[MODIFY\]\s+.+)', content)
    result = []
    for idx, part in enumerate(parts):
        result.append(part)
        if re.match(r'####\s+\[MODIFY\]\s+', part) and idx + 1 < len(parts):
            body = parts[idx + 1]
            has_sr = re.search(r'<<<SEARCH', body)
            has_fence = re.search(r'(?:^|\n)\s*(`{3,}|~{3,})', body)
            if has_sr and not has_fence:
                # Infer language from file extension
                path_match = re.search(r'\[MODIFY\]\s+(.+)', part)
                path = path_match.group(1).strip().strip('`') if path_match else ""
                # Strip escaped underscores for clean extension detection
                path_clean = path.replace('\\_', '_')
                ext = "." + path_clean.rsplit(".", 1)[-1] if "." in path_clean else ""
                lang = ext_lang.get(ext, "python")
                body_stripped = body.strip('\n')
                parts[idx + 1] = f"\n```{lang}\n{body_stripped}\n```\n"
                logger.warning(
                    "auto_fenced_modify_block",
                    extra={"path": path, "lang": lang},
                )
    return "".join(result)


def _dedup_modify_blocks(content: str) -> str:
    """Remove duplicate [NEW] and [MODIFY] blocks for the same file path.

    When the AI generates multiple blocks for the same file across
    different steps, only the FIRST occurrence is kept. Later occurrences
    are replaced with a cross-reference comment.

    This is a deterministic safety net for the one-file-one-block rule
    enforced via the prompt constraints.
    """
    # Track which files have been seen in any block type
    seen_files: Dict[str, tuple] = {}  # path -> (step_number, action)
    duplicates_removed = 0

    # Match NEW or MODIFY headers with their content up to next #### or ### header
    pattern = re.compile(
        r'(####\s+\[(NEW|MODIFY)\]\s+(.+?)\n)'
        r'(.*?)'
        r'(?=####\s+\[|###\s+|\Z)',
        re.DOTALL,
    )

    def _replace_duplicate(match: re.Match) -> str:
        nonlocal duplicates_removed
        action = match.group(2)
        file_path = match.group(3).strip().strip('`')

        # Extract step number from surrounding context
        step_match = re.search(
            r'### Step (\d+):.*?$',
            content[:match.start()],
            re.MULTILINE,
        )
        current_step = int(step_match.group(1)) if step_match else 0

        if file_path in seen_files:
            duplicates_removed += 1
            original_step, original_action = seen_files[file_path]
            logger.warning(
                "dedup_file_block",
                extra={
                    "file": file_path,
                    "original_step": original_step,
                    "original_action": original_action,
                    "duplicate_step": current_step,
                    "duplicate_action": action,
                },
            )
            return (
                f"<!-- DEDUP: {file_path} already [{original_action}] in Step "
                f"{original_step}. All changes for this file should be "
                f"consolidated there. -->\n\n"
            )
        else:
            seen_files[file_path] = (current_step, action)
            return match.group(0)  # Keep original

    result = pattern.sub(_replace_duplicate, content)

    if duplicates_removed > 0:
        console.print(
            f"[yellow]🔧 Dedup: Removed {duplicates_removed} duplicate "
            f"file block(s) (one-file-one-block rule)[/yellow]"
        )

    return result


def _escape_dunder_paths(content: str) -> str:
    r"""Escape double underscores in [NEW/MODIFY/DELETE] header paths.

    Markdown interprets ``__init__`` as bold (``**init**``). This pass
    finds file paths in block headers and escapes ``__`` → ``\_\_`` so
    the path renders literally.
    """
    def _escape_path(match: re.Match) -> str:
        prefix = match.group(1)  # e.g. '#### [MODIFY] '
        path = match.group(2)
        # Only escape __ that are part of Python dunder names
        escaped = path.replace('__', r'\_\_')
        return f"{prefix}{escaped}"

    return re.sub(
        r'(####\s+\[(?:NEW|MODIFY|DELETE)\]\s+)(.+)',
        _escape_path,
        content,
    )


def generate_runbook_chunked(
    story_id: str,
    story_content: str,
    rules_content: str,
    targeted_context: str,
    source_tree: str,
    source_code: str,
    provider: Optional[str] = None,
    timeout: int = 180,
    checkpoint_path: Optional[Path] = None,
) -> str:
    """Execute a modular, two-phase generation pipeline for detailed runbooks.

    Phase 1 generates a JSON Skeleton (table of contents), Phase 2 populates
    each section with detailed implementation blocks.

    Args:
        story_id: The story identifier.
        story_content: Full content of the user story.
        rules_content: Relevant governance rules.
        targeted_context: Codebase introspection data.
        source_tree: The project file structure.
        source_code: Outlines of relevant source files.
        provider: AI provider override.
        timeout: Request timeout in seconds.

    Returns:
        The fully assembled implementation runbook in Markdown.
    """
    from agent.core.ai import ai_service

    if provider:
        ai_service.set_provider(provider)

    # Initialise token tracker for this generation run (AC: Scenario 2)
    tracker = UsageTracker() if UsageTracker is not None else None
    _model_hint = provider or "default"

    context_summary = (
        f"{source_tree}\n\n{source_code}\n\n{targeted_context}\n\nRULES:\n{rules_content}"
    )

    # Phase 1: Skeleton Generation
    with tracer.start_as_current_span("runbook.skeleton_generation") as span:
        skeleton_prompt = generate_skeleton_prompt(story_content)
        console.print("[bold green]\U0001f916 Phase 1: Generating Skeleton...[/bold green]")

        skeleton_raw = ai_service.complete(
            system_prompt="You are a senior technical architect. Output ONLY valid JSON.",
            user_prompt=skeleton_prompt,
        )
        if tracker is not None:
            tracker.record_call(
                _model_hint,
                _token_count(skeleton_prompt),
                _token_count(skeleton_raw),
            )

        try:
            if "SPLIT_REQUEST" in skeleton_raw:
                return skeleton_raw
                
            skeleton_data = _extract_json(skeleton_raw)
            if skeleton_data.get("SPLIT_REQUEST"):
                return skeleton_raw
                
            skeleton = GenerationSkeleton.from_dict(skeleton_data)
            span.set_attribute("section_count", len(skeleton.sections))
            logger.info(
                "skeleton_generated",
                extra={"story_id": story_id, "size": len(skeleton_raw)},
            )
        except (json.JSONDecodeError, ValueError) as exc:
            if "SPLIT_REQUEST" in skeleton_raw:
                return skeleton_raw
                
            error_console.print(
                f"[bold red]\u274c Failed to parse Skeleton JSON: {exc}[/bold red]"
            )
            logger.error(
                "skeleton_parse_failed",
                extra={"error": str(exc), "story_id": story_id},
            )
            raise typer.Exit(code=1)

    # Phase 2: Block Generation
    # Auto-resume: if a .partial checkpoint exists from a previous interrupted run,
    # seed assembled_content from it and skip already-completed steps.
    completed_steps = 0
    if checkpoint_path and checkpoint_path.exists() and checkpoint_path.is_file():
        try:
            partial_content = checkpoint_path.read_text(encoding="utf-8")
            completed_steps = len(re.findall(r'^### Step \d+:', partial_content, re.MULTILINE))
            assembled_content = partial_content
            console.print(
                f"[yellow]⏩ Resuming from checkpoint: {completed_steps} section(s) already complete.[/yellow]"
            )
            logger.info(
                "runbook_checkpoint_resumed",
                extra={"story_id": story_id, "completed_steps": completed_steps, "checkpoint": str(checkpoint_path)},
            )
        except OSError:
            assembled_content = (
                f"# Runbook: {skeleton.title}\n\n## State\n\nPROPOSED\n\n"
                f"## Implementation Steps\n\n"
            )
    else:
        assembled_content = (
            f"# Runbook: {skeleton.title}\n\n## State\n\nPROPOSED\n\n"
            f"## Implementation Steps\n\n"
        )

    # Track changes made by previous sections to prevent duplication
    prior_changes: Dict[str, str] = {}

    # Build the Oracle of existing files from the FILESYSTEM, not the AI skeleton.
    # The skeleton's files lists are AI-generated and incomplete — files the AI doesn't
    # explicitly mention (e.g. __init__.py, helper modules) are invisible, causing
    # [NEW] on files that already exist on disk.  A filesystem glob gives complete
    # ground truth for all files the AI could plausibly touch.
    repo_root = Path.cwd()
    _oracle_globs = [
        "*",              # root-level files: CHANGELOG.md, README.md, .coveragerc, etc.
        ".agent/src/**/*",
        ".agent/tests/**/*",
        "tests/**/*",
        "backend/**/*",
        ".agent/*.toml",
        ".agent/*.md",
        ".agent/rules/**/*",
        ".agent/docs/**/*",
    ]
    all_existing_files: List[str] = []
    for pattern in _oracle_globs:
        for p in repo_root.glob(pattern):
            if p.is_file():
                try:
                    rel = str(p.relative_to(repo_root))
                    if rel not in all_existing_files:
                        all_existing_files.append(rel)
                except ValueError:
                    pass

    # NOTE: modify_contents is now loaded per-block (inside the loop below)
    # so each block always sees the *current* on-disk state rather than a
    # stale pre-run snapshot.  This eliminates the primary source of hallucinated
    # <<<SEARCH blocks where earlier blocks had already changed the file.


    # ─────────────────────────────────────────────────────────────────────
    # Phase 2a: Pre-load modify targets and build block prompts
    # Sequential + lightweight — fast local I/O that prepares all inputs
    # before the parallel AI-generation stage that follows.
    # ─────────────────────────────────────────────────────────────────────
    section_inputs: List[Any] = []  # [(i, section, prompt, modify_contents)]
    all_modify_contents: Dict[str, str] = {}  # accumulated for sr_validation

    for i, section in enumerate(skeleton.sections, 1):
        if i <= completed_steps:
            console.print(
                f"[dim]⏭  Skipping section {i}/{len(skeleton.sections)} "
                f"(already checkpointed): {section.title}[/dim]"
            )
            continue

        modify_contents: Dict[str, str] = {}
        for fpath in section.files:
            try:
                p = (repo_root / fpath).resolve()
                if p.exists() and p.is_file() and p.is_relative_to(repo_root):
                    modify_contents[fpath] = p.read_text(encoding="utf-8")
            except OSError:
                pass
        all_modify_contents.update(modify_contents)

        if modify_contents:
            logger.info(
                "modify_targets_loaded",
                extra={
                    "section": section.title,
                    "files": list(modify_contents.keys()),
                    "total_chars": sum(len(v) for v in modify_contents.values()),
                },
            )

        # INFRA-181: use structured JSON ops unless legacy mode is active
        _legacy_mode = os.environ.get("RUNBOOK_GENERATION_LEGACY") == "1"
        block_prompt = generate_block_prompt(
            section.title,
            section.description,
            skeleton_raw,
            story_content,
            context_summary,
            prior_changes=None,  # omitted for parallel; dedup handled in Phase 2c
            modify_file_contents=modify_contents or None,
            existing_files=all_existing_files or None,
            legacy=_legacy_mode,
        )
        section_inputs.append((i, section, block_prompt, modify_contents))

    # ─────────────────────────────────────────────────────────────────────
    # Phase 2b: Two-Pass Parallel block generation via TaskExecutor
    # ─────────────────────────────────────────────────────────────────────
    async def _run_parallel_blocks(inputs: List[Any], pass_name: str) -> List[Dict[str, Any]]:
        async def _gen(step: int, prompt: str) -> Dict[str, Any]:
            raw = await asyncio.to_thread(
                ai_service.complete,
                "You are an implementation specialist. Output ONLY valid JSON.",
                prompt,
            )
            if tracker is not None:
                tracker.record_call(_model_hint, _token_count(prompt), _token_count(raw))
            return {"step": step, "raw": raw}

        if not inputs: return []
        task_exe = TaskExecutor(max_concurrency=3)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console, transient=True) as prog:
            pbar = prog.add_task(f"[bold blue]⚡ {pass_name}: Generating {len(inputs)} blocks...", total=len(inputs))
            return await task_exe.run_parallel([(lambda s=step, p=prompt: _gen(s, p)) for step, _, prompt, _ in inputs], on_progress=lambda _: prog.advance(pbar))

    pass_1_inputs = [i for i in section_inputs if not _is_verification_section(i[1])]
    pass_2_inputs = [i for i in section_inputs if _is_verification_section(i[1])]

    def _run_async(c: Any) -> Any:
        try: return asyncio.run(c)
        except RuntimeError:
            l = asyncio.new_event_loop()
            try: return l.run_until_complete(c)
            finally: l.close()

    _par_results_1 = _run_async(_run_parallel_blocks(pass_1_inputs, "Pass 1 (Implementation)"))
    raw_by_step: Dict[int, str] = {}
    pass_1_context = []

    for _r in _par_results_1:
        if _r["status"] == "success":
            raw_by_step[_r["data"]["step"]] = _r["data"]["raw"]
            try:
                b = GenerationBlock.from_dict(_extract_json(_r["data"]["raw"]))
                # INFRA-181: assemble from ops when content field is empty
                b_content = b.content if b.content else _assemble_block_from_json(b)
                pass_1_context.append(f"### {b.header}\n\n{b_content}")
            except Exception: pass
        else:
            logger.error("block_parallel_generation_failed", extra={"index": _r["index"], "error": _r.get("error", "")})

    if pass_2_inputs:
        if pass_1_inputs and not pass_1_context:
            logger.error("pass_1_failed_aborting_pass_2", extra={"detail": "Pass 1 yielded no code; aborting Pass 2"})
            for step, sec, _, _ in pass_2_inputs:
                raw_by_step[step] = f"{{\"header\": \"{sec.title}\", \"content\": \"[Aborted: Pass 1 Failed]\"}}"
        else:
            pass_1_compiled = "\n".join(pass_1_context) if pass_1_context else None
            new_pass_2_inputs = []
            for step, sec, _old_prompt, mod_contents in pass_2_inputs:
                b_prompt = generate_block_prompt(
                    sec.title, sec.description, skeleton_raw, story_content, context_summary,
                    None, mod_contents or None, all_existing_files or None, pass_1_compiled
                )
                new_pass_2_inputs.append((step, sec, b_prompt, mod_contents))
            
            for _r in _run_async(_run_parallel_blocks(new_pass_2_inputs, "Pass 2 (Verification)")):
                if _r["status"] == "success":
                    raw_by_step[_r["data"]["step"]] = _r["data"]["raw"]
                else:
                    logger.error("block_parallel_generation_failed", extra={"index": _r["index"], "error": _r.get("error", "")})

    # ─────────────────────────────────────────────────────────────────────
    # Phase 2c: Sequential assembly — parse, clean, dedup, checkpoint
    # Results are processed in section order for deterministic output.
    # ─────────────────────────────────────────────────────────────────────
    for i, section, _prompt, modify_contents in section_inputs:
        with tracer.start_as_current_span("runbook.block_assembly") as bspan:
            bspan.set_attribute("section_index", i)
            bspan.set_attribute("section_title", section.title)

            console.print(
                f"[bold green]🔵 Phase 2c: Assembling Block "
                f"{i}/{len(skeleton.sections)}: {section.title}...[/bold green]"
            )

            if i not in raw_by_step:
                error_console.print(
                    f"[bold red]❌ Block {i} ('{section.title}') "
                    f"failed in parallel generation — skipping.[/bold red]"
                )
                logger.error(
                    "block_assembly_skipped",
                    extra={"step": i, "section": section.title},
                )
                assembled_content += (
                    f"## {section.title}\n\n"
                    "[Generation failed — parallel execution error]\n\n"
                )
                continue

            block_raw = raw_by_step[i]

            parse_ok = False
            last_error = None
            for attempt in range(3):  # 2 retries on parse failure
                try:
                    block_data = _extract_json(block_raw)
                    block = GenerationBlock.from_dict(block_data)
                    parse_ok = True
                    break
                except (json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    if attempt < 2:
                        console.print(
                            f"[yellow]⚠️  Block JSON parse failed for "
                            f"'{section.title}': {exc} — retrying "
                            f"({attempt + 1}/2)...[/yellow]"
                        )
                        logger.warning(
                            "block_parse_retry",
                            extra={"section": section.title, "error": str(exc), "attempt": attempt + 1},
                        )
                        # Retry: re-prompt the AI with the specific error feedback.
                        # Use _prompt (per-section) not block_prompt (stale loop variable).
                        block_raw = ai_service.complete(
                            system_prompt=(
                                "You are an implementation specialist. Output ONLY valid JSON. "
                                "Your previous response had a JSON syntax error: "
                                f"{exc}. "
                                "Ensure all strings are properly escaped (especially quotes "
                                "and newlines inside code blocks). Do NOT wrap your "
                                "response in markdown fences."
                            ),
                            user_prompt=_prompt,
                        )


            if parse_ok:
                # INFRA-181: assemble markdown from structured ops; falls back
                # to legacy content string when ops list is empty.
                cleaned = _assemble_block_from_json(block)
                # Safety net: strip leading ## or ### headers (legacy path)
                cleaned = cleaned.lstrip("\n")
                cleaned = re.sub(
                    r'^#{2,3}\s+[^\n]*\n+', '', cleaned, count=1,
                )
                # Per-block: demote any remaining ### sub-headers to **bold**.
                # The AI reliably ignores Rule 14 for sub-sections like
                # ### Troubleshooting or ### 1. Setup — demotion must happen
                # here so checkpoints are also clean, not just the final write.
                def _demote(m: re.Match) -> str:
                    txt = m.group(1).strip()
                    # Never demote the real "Step N:" anchors written by the pipeline
                    if re.match(r'^Step \d+', txt):
                        return m.group(0)
                    return f'**{txt}**'

                _cleaned_demoted = re.sub(r'^### (.+)$', _demote, cleaned, flags=re.MULTILINE)
                if _cleaned_demoted != cleaned:
                    _n = len(re.findall(r'^### ', cleaned, re.MULTILINE)) - len(
                        re.findall(r'^### ', _cleaned_demoted, re.MULTILINE)
                    )
                    logger.debug(
                        "block_headers_demoted",
                        extra={"section": section.title, "count": _n},
                    )
                    cleaned = _cleaned_demoted

                # Blank line before code fences (prevents markdownlint failures)
                cleaned = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', cleaned)

                # Deterministic duplicate-file strip: remove any file operation
                # blocks that target files already handled by prior sections.
                # The AI ignores the FORBIDDEN FILES prompt — this catches it.
                if prior_changes:
                    _forbidden = set(prior_changes.keys())
                    # Remove the entire #### [NEW/MODIFY/DELETE] <path> block
                    # for forbidden paths. For [NEW]: header + fenced code.
                    # For [MODIFY]: header + S/R fences. For [DELETE]: header + rationale.
                    _dup_removed = 0
                    for _fpath in _forbidden:
                        _escaped = re.escape(_fpath)
                        # Match header and everything until next #### header or end
                        _dup_pat = re.compile(
                            r'####\s+\[(?:NEW|MODIFY|DELETE)\]\s+' + _escaped
                            + r'[^\n]*\n(?:(?!####\s+\[).)*',
                            re.DOTALL,
                        )
                        _before = cleaned
                        cleaned = _dup_pat.sub('', cleaned)
                        if cleaned != _before:
                            _dup_removed += 1
                    if _dup_removed:
                        logger.info(
                            "block_duplicate_ops_removed",
                            extra={"section": section.title, "count": _dup_removed},
                        )
                        console.print(
                            f"[dim]🔧 Dedup: Removed {_dup_removed} duplicate "
                            f"file block(s) from Step {i} (one-file-one-block rule)[/dim]"
                        )

                # INFRA-181: fences are injected by _assemble_block_from_json;
                # legacy fallback still runs _ensure_* passes for content-mode blocks.
                if not block.ops:
                    cleaned = _ensure_new_blocks_fenced(cleaned)
                    cleaned = _ensure_modify_blocks_fenced(cleaned)

                # ─────────────────────────────────────────────────────────────
                # Block-type validation: [NEW] must not target files that exist
                # on disk. The parallel generation model sometimes confuses
                # [NEW] / [MODIFY] despite instructions in the block prompt.
                # Detect here (earliest point after fencing) and regenerate
                # the block with an explicit correction, including the
                # accumulated prior_changes so the model has full session context.
                # ─────────────────────────────────────────────────────────────
                _new_on_existing: List[str] = [
                    _np.strip().strip("`")
                    for _np in re.findall(r"####\s+\[NEW\]\s+([^\n`]+)", cleaned)
                    if _np.strip().strip("`") in all_existing_files
                ]
                if _new_on_existing:
                    console.print(
                        f"[yellow]⚠️  Block {i} '{section.title}' used "
                        f"[NEW] for existing file(s) {_new_on_existing} "
                        f"— regenerating with correction...[/yellow]"
                    )
                    logger.warning(
                        "block_new_on_existing_detected",
                        extra={"section": section.title, "step": i, "files": _new_on_existing},
                    )
                    _correction_sys = (
                        "You are an implementation specialist. Output ONLY valid JSON.\n"
                        "CORRECTION REQUIRED: Your previous response used [NEW] for "
                        "file(s) that already exist on disk. For existing files you MUST "
                        "use [MODIFY] with <<<SEARCH/===/>>> blocks; [NEW] creates a new "
                        "file from scratch. The current file content has been provided in "
                        "the user prompt — use lines from it verbatim as your SEARCH "
                        "anchor (exact whitespace matters).\n\n"
                        "Files incorrectly marked [NEW]:\n"
                        + "\n".join(f"  - `{_p}`" for _p in _new_on_existing)
                    )
                    if prior_changes:
                        _correction_sys += (
                            "\n\nAlready completed in prior steps (do NOT re-implement):\n"
                            + "\n".join(
                                f"  - {_k}: {_v.splitlines()[0]}"
                                for _k, _v in list(prior_changes.items())[-8:]
                            )
                        )
                    for _bt_retry in range(2):
                        _corrected_raw = ai_service.complete(
                            system_prompt=_correction_sys,
                            user_prompt=_prompt,
                        )
                        if tracker is not None:
                            tracker.record_call(
                                _model_hint,
                                _token_count(_prompt),
                                _token_count(_corrected_raw),
                            )
                        try:
                            _corrected_block = GenerationBlock.from_dict(
                                _extract_json(_corrected_raw)
                            )
                            _corrected_cleaned = _corrected_block.content.lstrip("\n")
                            # Verify the correction actually fixed it
                            _still_bad = [
                                _np.strip().strip("`")
                                for _np in re.findall(
                                    r"####\s+\[NEW\]\s+([^\n`]+)", _corrected_cleaned
                                )
                                if _np.strip().strip("`") in all_existing_files
                            ]
                            if not _still_bad:
                                cleaned = _corrected_cleaned
                                block = _corrected_block
                                logger.info(
                                    "block_type_corrected",
                                    extra={
                                        "section": section.title,
                                        "step": i,
                                        "attempt": _bt_retry + 1,
                                        "fixed": _new_on_existing,
                                    },
                                )
                                break
                            logger.warning(
                                "block_type_correction_partial",
                                extra={
                                    "section": section.title,
                                    "still_bad": _still_bad,
                                    "attempt": _bt_retry + 1,
                                },
                            )
                        except (json.JSONDecodeError, ValueError):
                            logger.warning(
                                "block_type_correction_parse_failed",
                                extra={"section": section.title, "attempt": _bt_retry + 1},
                            )

                # Per-block S/R pre-validation: reanchor hallucinated SEARCH
                # blocks now, using the file contents we already loaded —
                # prevents errors from stacking up until write time.
                try:
                    from agent.core.implement.sr_validation import (
                        validate_and_correct_sr_blocks as _sr_validate,
                    )
                    # Lazy-load content for off-skeleton MODIFY targets: the AI
                    # may generate [MODIFY] for files not in skeleton.files, so
                    # their content was never injected into the prompt. Load them
                    # now so the S/R validator has ground truth to reanchor against.
                    _modify_paths = re.findall(
                        r'####\s+\[MODIFY\]\s+([^\n`]+)', cleaned,
                    )
                    for _mp in _modify_paths:
                        _mp = _mp.strip().strip('`')
                        if _mp and _mp not in all_modify_contents:
                            _mp_path = Path(_mp) if Path(_mp).is_absolute() else Path.cwd() / _mp
                            if _mp_path.exists():
                                try:
                                    all_modify_contents[_mp] = _mp_path.read_text(encoding="utf-8")
                                    logger.debug(
                                        "off_skeleton_modify_loaded",
                                        extra={"file": _mp, "section": section.title},
                                    )
                                except OSError:
                                    pass
                    _block_stub = f"### Step {i}: {block.header}\n\n{cleaned}\n\n"
                    _corrected_stub, _sr_total, _sr_fixed = _sr_validate(_block_stub)
                    if _sr_fixed:
                        # Extract corrected content back out of the stub wrapper
                        _stub_prefix = f"### Step {i}: {block.header}\n\n"
                        if _corrected_stub.startswith(_stub_prefix):
                            cleaned = _corrected_stub[len(_stub_prefix):].rstrip("\n")
                        logger.info(
                            "block_sr_prevalidated",
                            extra={"section": section.title, "total": _sr_total, "fixed": _sr_fixed},
                        )
                except Exception as _sr_exc:  # noqa: BLE001
                    logger.debug("block_sr_prevalidation_skipped: %s", _sr_exc)

                assembled_content += f"### Step {i}: {block.header}\n\n{cleaned}\n\n"

                # Checkpoint: persist completed blocks so timeouts don't lose progress
                if checkpoint_path:
                    try:
                        checkpoint_path.write_text(assembled_content, encoding="utf-8")
                        logger.debug(
                            "runbook_checkpoint_written",
                            extra={"section": i, "path": str(checkpoint_path)},
                        )
                    except OSError:
                        pass  # non-fatal — checkpoint is best-effort

                # Extract file changes with summaries for deduplication
                # INFRA-181: extract file ops from structured ops list when available;
                # fall back to regex over assembled markdown for the legacy path.
                if block.ops:
                    file_blocks = [
                        (str(op.get("op", "modify")).upper(), op.get("file", ""))
                        for op in block.ops
                        if op.get("file")
                    ]
                else:
                    file_blocks = re.findall(
                        r'####\s+\[(NEW|MODIFY|DELETE)\]\s+(.+?)(?:\n|$)',
                        cleaned,
                    )
                for action, path in file_blocks:
                    clean = path.strip().strip('`')
                    if not clean:
                        continue
                    if action == "NEW":
                        # Validate: [NEW] must target files that don't exist yet.
                        # Note: block-type correction was already attempted earlier
                        # in Phase 2c (before S/R pre-validation). If the file still
                        # appears as [NEW] here the correction retries were exhausted.
                        from agent.core.config import resolve_repo_path as _resolve_repo
                        _new_path = _resolve_repo(clean)
                        if _new_path and _new_path.exists():
                            logger.warning(
                                "new_block_targets_existing_file",
                                extra={"file": clean, "step": i, "section": section.title},
                            )
                        # Extract the actual code content for this [NEW] block
                        # so later sections can write accurate SEARCH blocks
                        new_code = ""
                        code_pattern = re.compile(
                            r'####\s+\[NEW\]\s+' + re.escape(path.strip())
                            + r'.*?\n+```\w*\n(.*?)```',
                            re.DOTALL,
                        )
                        code_match = code_pattern.search(cleaned)
                        if code_match:
                            new_code = code_match.group(1).strip()
                        if new_code:
                            prior_changes[clean] = (
                                f"[NEW] created in Step {i} ({section.title})\n"
                                f"Content created:\n```\n{new_code}\n```"
                            )
                        else:
                            prior_changes[clean] = (
                                f"[NEW] created in Step {i} ({section.title})"
                            )
                    elif action == "DELETE":
                        prior_changes[clean] = f"[DELETE] removed in Step {i} ({section.title})"
                    elif action == "MODIFY":
                        prior_changes[clean] = f"[MODIFY] changed in Step {i} ({section.title})"

                logger.info(
                    "block_generated",
                    extra={
                        "section": section.title,
                        "size": len(block_raw),
                        "files_touched": len(file_blocks),
                        "total_prior_files": len(prior_changes),
                        "op_count": len(block.ops),
                        "structured": bool(block.ops),
                    },
                )
            else:
                error_console.print(
                    f"[bold red]❌ Failed to parse Block JSON for "
                    f"'{section.title}' after retry: {last_error}[/bold red]"
                )
                logger.error(
                    "block_parse_failed",
                    extra={"section": section.title, "error": str(last_error)},
                )
                # Best effort: placeholder for failed section
                assembled_content += (
                    f"## {section.title}\n\n"
                    "[Generation failed for this section — JSON parse error]\n\n"
                )

    # Post-generation passes (order matters)
    # INFRA-181: _ensure_modify_blocks_fenced and _rebalance_fences are no longer
    # needed when all blocks use the structured ops path (fences are injected by
    # _assemble_block_from_json). They are retained here only as a safety net for
    # mixed legacy/structured runs and will be removed in INFRA-181-S4.
    assembled_content = _ensure_modify_blocks_fenced(assembled_content)
    assembled_content = _dedup_modify_blocks(assembled_content)
    assembled_content = _escape_dunder_paths(assembled_content)
    assembled_content = _rebalance_fences(assembled_content)
    # Normalise list markers: * → -, double-space → single-space (MD004/MD030)
    assembled_content = _normalize_list_markers(assembled_content)
    # Rewrite # Changelog in S/R SEARCH blocks to avoid MD024/MD025
    assembled_content = _fix_changelog_sr_headings(assembled_content)
    # Ensure blank lines surround fenced blocks (MD031)
    assembled_content = _ensure_blank_lines_around_fences(assembled_content)

    if tracker is not None:
        tracker.print_summary()

    return assembled_content
