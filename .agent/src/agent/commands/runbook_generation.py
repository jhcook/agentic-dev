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

    # Try extracting the first {...} object
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

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


def generate_runbook_chunked(
    story_id: str,
    story_content: str,
    rules_content: str,
    targeted_context: str,
    source_tree: str,
    source_code: str,
    provider: Optional[str] = None,
    timeout: int = 180,
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
    assembled_content = (
        f"# Runbook: {skeleton.title}\n\n## State\n\nPROPOSED\n\n"
        f"## Implementation Steps\n\n"
    )

    # Track changes made by previous sections to prevent duplication
    prior_changes: Dict[str, str] = {}

    for i, section in enumerate(skeleton.sections, 1):
        with tracer.start_as_current_span("runbook.block_generation") as bspan:
            bspan.set_attribute("section_index", i)
            bspan.set_attribute("section_title", section.title)

            console.print(
                f"[bold green]\U0001f916 Phase 2: Generating Block "
                f"{i}/{len(skeleton.sections)}: {section.title}...[/bold green]"
            )

            # Layer 1 S/R fix: read actual file content for MODIFY targets
            # so the AI has ground truth when writing <<<SEARCH blocks.
            modify_contents: Dict[str, str] = {}
            for fpath in section.files:
                try:
                    p = Path(fpath)
                    if not p.is_absolute():
                        p = Path.cwd() / fpath
                    if p.exists() and p.is_file():
                        modify_contents[fpath] = p.read_text(encoding="utf-8")
                except OSError:
                    pass  # unreadable — skip silently

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
            )

            block_raw = ai_service.complete(
                system_prompt="You are an implementation specialist. Output ONLY valid JSON.",
                user_prompt=block_prompt,
            )

            parse_ok = False
            last_error = None
            for attempt in range(2):  # 1 retry on parse failure
                try:
                    block_data = _extract_json(block_raw)
                    block = GenerationBlock.from_dict(block_data)
                    parse_ok = True
                    break
                except (json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    if attempt == 0:
                        console.print(
                            f"[yellow]⚠️  Block JSON parse failed for "
                            f"'{section.title}': {exc} — retrying...[/yellow]"
                        )
                        logger.warning(
                            "block_parse_retry",
                            extra={"section": section.title, "error": str(exc)},
                        )
                        # Retry: re-prompt the AI with the error feedback
                        block_raw = ai_service.complete(
                            system_prompt=(
                                "You are an implementation specialist. Output ONLY valid JSON. "
                                "Your previous response had a JSON syntax error. "
                                "Ensure all strings are properly escaped (especially quotes "
                                "and newlines inside code blocks)."
                            ),
                            user_prompt=block_prompt,
                        )

            if parse_ok:
                # Safety net: strip leading ## or ### headers the AI may
                # have included despite prompt instructions
                cleaned = block.content.lstrip("\n")
                cleaned = re.sub(
                    r'^#{2,3}\s+[^\n]*\n+', '', cleaned, count=1,
                )
                # Auto-fence: ensure [NEW] blocks have fenced code content
                cleaned = _ensure_new_blocks_fenced(cleaned)
                assembled_content += f"### Step {i}: {block.header}\n\n{cleaned}\n\n"

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

    return assembled_content
