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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.logger import get_logger
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt


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
    content: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationBlock":
        """Build from the JSON dict returned by the AI."""
        return cls(
            header=data.get("header", data.get("title", "Untitled")),
            content=data.get("content", data.get("body", "")),
        )

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()
error_console = Console(stderr=True)


def _extract_json(raw: str) -> Dict[str, Any]:
    """Robustly extract a JSON object from AI output.

    Handles:
    - Raw JSON strings
    - JSON wrapped in markdown ```json fences
    - Leading/trailing garbage text around JSON
    - Balanced brace extraction for nested objects

    Args:
        raw: Raw AI response text.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If no valid JSON can be extracted.
    """
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


def _ensure_new_blocks_fenced(content: str) -> str:
    """Wrap unfenced [NEW] block content in code fences.

    Scans for ``#### [NEW] <path>`` headers and checks if the content
    between that header and the next ``####`` / ``###`` header is fenced.
    If not, wraps it in a fenced code block with language inferred from
    the file extension.
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
                # Wrap the body in fences
                body_stripped = body.strip('\n')
                parts[idx + 1] = f"\n```{lang}\n{body_stripped}\n```\n"
    return "".join(result)


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
    """Escape double underscores in [NEW/MODIFY/DELETE] header paths.

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

        try:
            skeleton_data = _extract_json(skeleton_raw)
            skeleton = GenerationSkeleton.from_dict(skeleton_data)
            span.set_attribute("section_count", len(skeleton.sections))
            logger.info(
                "skeleton_generated",
                extra={"story_id": story_id, "size": len(skeleton_raw)},
            )
        except (json.JSONDecodeError, ValueError) as exc:
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
        ".agent/src/**/*",
        ".agent/tests/**/*",
        "tests/**/*",
    ]
    all_existing_files: List[str] = []
    for pattern in _oracle_globs:
        for p in repo_root.glob(pattern):
            if p.is_file():
                try:
                    rel = str(p.relative_to(repo_root))
                    all_existing_files.append(rel)
                except ValueError:
                    pass

    # Pre-load content for MODIFY targets — section-scoped only.
    # The vector index (context_summary) handles broad content relevance;
    # modify_contents is a targeted supplement so the AI gets exact text for
    # <<<SEARCH blocks for files this section explicitly owns.
    # Using all_existing_files here would inject hundreds of files → context overflow.
    all_modify_contents: Dict[str, str] = {}
    for s in skeleton.sections:
        for fpath in s.files:
            try:
                p = Path(fpath)
                if not p.is_absolute():
                    p = Path.cwd() / fpath
                if p.exists() and p.is_file():
                    all_modify_contents[fpath] = p.read_text(encoding="utf-8")
            except OSError:
                pass  # unreadable — skip silently


    for i, section in enumerate(skeleton.sections, 1):
        # Skip sections already written to the checkpoint
        if i <= completed_steps:
            console.print(f"[dim]⏭  Skipping section {i}/{len(skeleton.sections)} (already checkpointed): {section.title}[/dim]")
            continue

        with tracer.start_as_current_span("runbook.block_generation") as bspan:
            bspan.set_attribute("section_index", i)
            bspan.set_attribute("section_title", section.title)

            console.print(
                f"[bold green]\U0001f916 Phase 2: Generating Block "
                f"{i}/{len(skeleton.sections)}: {section.title}...[/bold green]"
            )

            # Layer 1 S/R fix: provide actual file content so the AI has ground
            # truth when writing <<<SEARCH blocks.
            # We pass ALL existing-file contents (not just this section's files)
            # because the AI may generate MODIFY blocks for files assigned to other sections.
            modify_contents = all_modify_contents

            if modify_contents:
                logger.info(
                    "modify_targets_loaded",
                    extra={
                        "section": section.title,
                        "files": list(modify_contents.keys()),
                        "total_chars": sum(len(v) for v in modify_contents.values()),
                    },
                )


            block_prompt = generate_block_prompt(
                section.title,
                section.description,
                skeleton_raw,
                story_content,
                context_summary,
                prior_changes=prior_changes if prior_changes else None,
                modify_file_contents=modify_contents if modify_contents else None,
                existing_files=all_existing_files if all_existing_files else None,
            )

            try:
                block_raw = ai_service.complete(
                    system_prompt="You are an implementation specialist. Output ONLY valid JSON.",
                    user_prompt=block_prompt,
                )
            except TimeoutError as exc:
                # Save whatever we have so far — next run auto-resumes from here
                if checkpoint_path and assembled_content:
                    try:
                        checkpoint_path.write_text(assembled_content, encoding="utf-8")
                    except OSError:
                        pass
                completed = i - 1
                remaining = len(skeleton.sections) - completed
                console.print(
                    f"\n[bold yellow]⏱  Block {i}/{len(skeleton.sections)} "
                    f"('{section.title}') timed out.[/bold yellow]\n"
                    f"[dim]  {completed} section(s) saved to checkpoint. "
                    f"{remaining} remaining.[/dim]\n"
                    f"[bold]  Re-run to resume automatically:[/bold]\n"
                    f"  [cyan]agent new-runbook {story_id} --timeout {int(str(exc).split()[-1].rstrip('s')) + 120 if str(exc).split()[-1].rstrip('s').isdigit() else 420}[/cyan]\n"
                )
                logger.warning(
                    "block_generation_timeout",
                    extra={"story_id": story_id, "section": section.title, "section_index": i},
                )
                raise typer.Exit(code=1)

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
                        # Retry: re-prompt the AI with the specific error feedback
                        block_raw = ai_service.complete(
                            system_prompt=(
                                "You are an implementation specialist. Output ONLY valid JSON. "
                                "Your previous response had a JSON syntax error: "
                                f"{exc}. "
                                "Ensure all strings are properly escaped (especially quotes "
                                "and newlines inside code blocks). Do NOT wrap your "
                                "response in markdown fences."
                            ),
                            user_prompt=block_prompt,
                        )

            if parse_ok:
                # Post-parse safety check: every step MUST have at least one
                # file operation. If the AI generated prose-only, retry once.
                _op_check = re.findall(
                    r'####\s+\[(NEW|MODIFY|DELETE)\]', block.content,
                )
                if not _op_check:
                    logger.warning(
                        "block_no_file_operations",
                        extra={"section": section.title, "step": i},
                    )
                    console.print(
                        f"[yellow]⚠️  Step {i} has no file operations — retrying "
                        f"with hard constraint...[/yellow]"
                    )
                    try:
                        _retry_prompt = (
                            block_prompt
                            + "\n\nCRITICAL: Your previous response contained NO "
                            "[NEW], [MODIFY], or [DELETE] blocks. This is a schema "
                            "violation. You MUST include at least one file operation. "
                            "If this section is procedural, emit a "
                            "[MODIFY] CHANGELOG.md block with the relevant entry."
                        )
                        _retry_raw = ai_service.complete(
                            system_prompt="You are an implementation specialist. Output ONLY valid JSON.",
                            user_prompt=_retry_prompt,
                        )
                        _retry_data = _extract_json(_retry_raw)
                        _retry_block = GenerationBlock.from_dict(_retry_data)
                        # Only accept the retry if it actually has ops now
                        if re.findall(r'####\s+\[(NEW|MODIFY|DELETE)\]', _retry_block.content):
                            block = _retry_block
                            logger.info(
                                "block_no_file_operations_retry_success",
                                extra={"section": section.title},
                            )
                        else:
                            logger.error(
                                "block_no_file_operations_retry_failed",
                                extra={"section": section.title},
                            )
                            console.print(
                                f"[bold red]❌ Step {i} still has no file "
                                f"operations after retry. Runbook will fail "
                                f"schema validation.[/bold red]"
                            )
                    except (json.JSONDecodeError, ValueError, TimeoutError) as _retry_exc:
                        logger.error(
                            "block_no_file_operations_retry_error",
                            extra={"section": section.title, "error": str(_retry_exc)},
                        )

                # Safety net: strip leading ## or ### headers the AI may
                # have included despite prompt instructions
                cleaned = block.content.lstrip("\n")
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

                # Auto-fence: ensure [NEW] blocks have fenced code content
                cleaned = _ensure_new_blocks_fenced(cleaned)
                cleaned = _ensure_modify_blocks_fenced(cleaned)

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
                file_blocks = re.findall(
                    r'####\s+\[(NEW|MODIFY|DELETE)\]\s+(.+?)(?:\n|$)',
                    block.content,
                )
                for action, path in file_blocks:
                    clean = path.strip().strip('`')
                    if not clean:
                        continue
                    if action == "NEW":
                        # Validate: [NEW] must target files that don't exist yet
                        from agent.core.config import resolve_repo_path as _resolve_repo
                        _new_path = _resolve_repo(clean)
                        if _new_path and _new_path.exists():
                            error_console.print(
                                f"[bold red]❌ File '{clean}' exists on disk but "
                                f"is marked as [NEW]. Use [MODIFY] with S/R blocks.[/bold red]"
                            )
                            logger.error(
                                "new_block_targets_existing_file file=%s step=%d",
                                clean, i,
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

    # Post-generation passes
    assembled_content = _ensure_modify_blocks_fenced(assembled_content)
    assembled_content = _dedup_modify_blocks(assembled_content)
    assembled_content = _escape_dunder_paths(assembled_content)

    return assembled_content
