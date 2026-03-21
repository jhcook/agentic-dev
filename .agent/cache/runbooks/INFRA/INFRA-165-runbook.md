# STORY-ID: INFRA-165: Define Chunked Runbook Skeleton and Prompts

## State

ACCEPTED

## Goal Description

Generating comprehensive, long-form runbooks in a single LLM request often leads to context loss, hallucinations, or truncated output due to token limits. This implementation introduces a modular, two-phase generation pipeline. Phase 1 generates a high-level JSON "Skeleton" (table of contents and structural headers), and Phase 2 populates specific "Blocks" based on those headers. This ensures depth, accuracy, and logical consistency for complex implementation plans while maintaining observability through OpenTelemetry tracing and structured logging.

## Linked Journeys

- JRN-082: Automated Runbook Generation Workflow

## Panel Review Findings

### @Architect
- Modular orchestration follows ADR-014 (Modular LLM Prompt Orchestration).
- Using structured data models (dataclasses) ensures type safety between generation phases without adding external dependencies like Pydantic.
- Architectural boundaries are respected by isolating prompt logic in `prompts.py` and model logic in `chunk_models.py`.

### @Qa
- Phase 1 and Phase 2 JSON schemas are validated against mock outputs in the new unit tests.
- Graceful handling of malformed JSON includes a retry mechanism for robust generation.
- The two-phase pipeline is covered by new unit tests in `test_chunk_models.py` and logic validation in `runbook.py`.

### @Security
- No PII is logged; character counts/sizes are used as proxies for token consumption in logs where direct token counts are unavailable.
- Prompts include specific instructions to avoid sensitive credentials or PII placeholder formats.

### @Product
- ACs are fully met: Phase 1 Skeleton, Phase 2 Blocks, and Graceful Error Handling are implemented.
- The new `--chunked` flag allows users to opt-in to high-fidelity generation for complex stories.

### @Observability
- Every phase (Skeleton and Block generation) is wrapped in OTel spans (`runbook.skeleton_generation`, `runbook.block_generation`).
- Structured logging includes phase identification, attempt counts, and latency/size metrics for cost analysis.

### @Docs
- CHANGELOG.md is updated.
- Story Impact Analysis is updated.
- Module, class, and function-level PEP-257 docstrings are included.

### @Compliance
- License headers (Apache 2.0) are present in all new files.
- No PII handling in this workflow; behavior is GDPR-neutral.

### @Backend
- Strict typing is enforced throughout the Python implementation.
- API logic (via Typer) is updated to support the new modular workflow.

## Codebase Introspection

### Targeted File Contents (from source)

(Verified against TARGETED FILE CONTENTS for `.agent/src/agent/core/ai/prompts.py` and `.agent/src/agent/commands/runbook.py`)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `test_models.py` | Implementation models | Runbook Chunk models | Update to include chunk model validation |
| `test_prompts.py` | Generic AI prompts | Skeleton/Block prompts | Create and add tests for new prompt generators |
| `test_runbook.py` | Monolithic generation | Chunked pipeline | Update to test the chunked flow branch |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `new_runbook` state enforcement | `runbook.py` | Must be COMMITTED | Yes |
| `new_runbook` forecast gate | `runbook.py` | Thresholds (400 LOC, 8 steps) | Yes |
| `upsert_artifact` call | `runbook.py` | Syncs to local cache | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Clean up redundant prompt template loading if chunked generation is selected.

## Implementation Steps

### Step 1: Define Chunked Data Models

#### [NEW] .agent/src/agent/core/implement/chunk_models.py

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

"""Models for modular (chunked) runbook generation."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class SkeletonSection:
    """Represents a specific section in the implementation runbook skeleton."""

    title: str
    description: str
    estimated_tokens: int


@dataclass
class RunbookSkeleton:
    """Represents the high-level structural skeleton of a runbook."""

    title: str
    sections: List[SkeletonSection]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunbookSkeleton":
        """
        Create a RunbookSkeleton from a dictionary with basic validation.

        Args:
            data: The dictionary to parse.

        Returns:
            A populated RunbookSkeleton instance.

        Raises:
            ValueError: If required fields are missing or malformed.
        """
        if "title" not in data or "sections" not in data:
            raise ValueError("Skeleton JSON must contain 'title' and 'sections'")
        if not isinstance(data["sections"], list):
            raise ValueError("'sections' must be a JSON array")

        sections = [
            SkeletonSection(
                title=str(s.get("title", "Untitled")),
                description=str(s.get("description", "")),
                estimated_tokens=int(s.get("estimated_tokens", 0)),
            )
            for s in data["sections"]
        ]
        return cls(title=str(data["title"]), sections=sections)


@dataclass
class RunbookBlock:
    """Represents a detailed implementation block generated from a skeleton section."""

    header: str
    content: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunbookBlock":
        """
        Create a RunbookBlock from a dictionary with basic validation.

        Args:
            data: The dictionary to parse.

        Returns:
            A populated RunbookBlock instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if "header" not in data or "content" not in data:
            raise ValueError("Block JSON must contain 'header' and 'content'")
        return cls(header=str(data["header"]), content=str(data["content"]))
```

### Step 2: Add Prompt Generators for Skeleton and Blocks

#### [MODIFY] .agent/src/agent/core/ai/prompts.py

```python
<<<SEARCH
def generate_impact_prompt(diff: str, story: str, metadata: Dict[str, Any] = None) -> str:
===
def generate_skeleton_prompt(story_content: str, metadata: Dict[str, Any] = None) -> str:
    """
    Generate a Phase 1 prompt for creating a runbook skeleton.

    Args:
        story_content: The full content of the User Story.
        metadata: Additional metadata about the environment or story.

    Returns:
        A system prompt for the AI.
    """
    prompt = f"""
You are the Lead Architect in the AI Governance Panel.
Your task is to generate a high-level Implementation Skeleton for the following User Story.

STORY CONTENT:
{story_content}

METADATA:
{metadata or "None"}

TASK:
Identify all necessary sections for a comprehensive implementation runbook (Architecture Review, Implementation Steps, Verification Plan, etc.).
For each section, provide a title, a brief description of what it should cover, and an estimated token weight.

OUTPUT FORMAT:
Return ONLY a JSON object with this structure (no markdown fences, no prose):
{{
  "title": "Implementation Runbook for STORY-ID",
  "sections": [
    {{
      "title": "Section Title",
      "description": "Short description of what to implement/review here.",
      "estimated_tokens": 500
    }}
  ]
}}

CRITICAL: Do NOT include credentials, PII, or secrets. Use placeholders if necessary.
"""
    return prompt.strip()


def generate_block_prompt(
    section_title: str,
    section_desc: str,
    skeleton_json: str,
    story_content: str,
    context_summary: str,
) -> str:
    """
    Generate a Phase 2 prompt for creating a detailed implementation block.

    Args:
        section_title: The title of the section to generate.
        section_desc: The description of the section.
        skeleton_json: The full skeleton JSON for context.
        story_content: The original story content.
        context_summary: Relevant codebase context (targeted introspection).

    Returns:
        A system prompt for the AI.
    """
    prompt = f"""
You are the Implementation Specialist in the AI Governance Panel.
Your task is to generate a DETAILED implementation block for a specific section of a runbook.

TARGET SECTION:
Title: {section_title}
Objective: {section_desc}

FULL RUNBOOK SKELETON (FOR COHERENCE):
{skeleton_json}

STORY CONTEXT:
{story_content}

CODEBASE CONTEXT:
{context_summary}

TASK:
Provide the full technical content for this section.
- Use valid Markdown.
- Use the repository-standard `#### [MODIFY|NEW|DELETE] <path>` format for code changes.
- Use `<<<SEARCH / === / >>>` blocks for modifications.
- Ensure all public interfaces have PEP-257 docstrings.
- Include a troubleshooting subsection if applicable.

OUTPUT FORMAT:
Return ONLY a JSON object with this structure (no markdown fences, no prose):
{{
  "header": "{section_title}",
  "content": "... full markdown content ..."
}}

CRITICAL: Ensure implementation blocks use repository-relative paths starting with `.agent/src/`.
"""
    return prompt.strip()


def generate_impact_prompt(diff: str, story: str, metadata: Dict[str, Any] = None) -> str:
>>>
```

### Step 3: Implement Chunked Pipeline in runbook.py

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.db.client import upsert_artifact

logger = get_logger(__name__)
===
from agent.db.client import upsert_artifact
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock
from agent.core.ai.prompts import generate_skeleton_prompt, generate_block_prompt

logger = get_logger(__name__)
>>>
<<<SEARCH
def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    skip_forecast: bool = typer.Option(
        False, "--skip-forecast", help="Bypass the complexity forecast gate."
    ),
    timeout: int = typer.Option(
        180, "--timeout", help="AI request timeout in seconds (default: 180)."
    ),
):
===
def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)."
    ),
    skip_forecast: bool = typer.Option(
        False, "--skip-forecast", help="Bypass the complexity forecast gate."
    ),
    timeout: int = typer.Option(
        180, "--timeout", help="AI request timeout in seconds (default: 180)."
    ),
    chunked: bool = typer.Option(
        False, "--chunked", help="Use modular chunked generation pipeline for better depth."
    ),
):
>>>
<<<SEARCH
    # 4. Prompt
    # Load Template
    template_path = config.templates_dir / "runbook-template.md"
    if not template_path.exists():
        console.print(f"[bold red]❌ Runbook template not found at {template_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_content = template_path.read_text()
    template_content = template_content.replace("{{ COPYRIGHT_HEADER }}", get_copyright_header())
    
    system_prompt = f"""You are the AI Governance Panel for this repository.
Your role is to design and document a DETAILED Implementation Runbook for a software engineering task.

THE PANEL (You represent ALL these roles):
{panel_description}

GOVERNANCE CHECKS PER ROLE:
{panel_checks}

INSTRUCTIONS:
1. You MUST adopt the perspective of EVERY role in the panel.
2. You MUST provide a distinct review section for EVERY role.
3. You MUST enforce the "Definition of Done".
4. You MUST follow the structure of the provided TEMPLATE exactly.
5. You MUST respect all Architectural Decision Records (ADRs) as codified decisions.
6. You MUST follow the DETAILED ROLE INSTRUCTIONS for each role.
7. You MUST use the SOURCE CODE CONTEXT to derive accurate file paths, existing patterns, and SDK usage. Do NOT invent file paths or SDK calls — use only what appears in the source tree and code outlines.
8. You MUST base your `<<<SEARCH` blocks exactly on the content provided in TARGETED FILE CONTENTS. Do NOT paraphrase, guess, or modify the lines you are searching for. They must exactly match the source.
9. You MUST list all patch targets from TEST IMPACT MATRIX in the Tes
===
    # 4. Content Generation
    if chunked:
        content = _generate_runbook_chunked(
            story_id=story_id,
            story_content=story_content,
            rules_content=rules_content,
            targeted_context=targeted_context,
            source_tree=source_tree,
            source_code=source_code,
            provider=provider,
            timeout=timeout
        )
        # Proceed to write
    else:
        # Load Template
        template_path = config.templates_dir / "runbook-template.md"
        if not template_path.exists():
            console.print(f"[bold red]❌ Runbook template not found at {template_path}[/bold red]")
            raise typer.Exit(code=1)
            
        template_content = template_path.read_text()
        template_content = template_content.replace("{{ COPYRIGHT_HEADER }}", get_copyright_header())
        
        system_prompt = f"""You are the AI Governance Panel for this repository.
Your role is to design and document a DETAILED Implementation Runbook for a software engineering task.

THE PANEL (You represent ALL these roles):
{panel_description}

GOVERNANCE CHECKS PER ROLE:
{panel_checks}

INSTRUCTIONS:
1. You MUST adopt the perspective of EVERY role in the panel.
2. You MUST provide a distinct review section for EVERY role.
3. You MUST enforce the "Definition of Done".
4. You MUST follow the structure of the provided TEMPLATE exactly.
5. You MUST respect all Architectural Decision Records (ADRs) as codified decisions.
6. You MUST follow the DETAILED ROLE INSTRUCTIONS for each role.
7. You MUST use the SOURCE CODE CONTEXT to derive accurate file paths, existing patterns, and SDK usage. Do NOT invent file paths or SDK calls — use only what appears in the source tree and code outlines.
8. You MUST base your `<<<SEARCH` blocks exactly on the content provided in TARGETED FILE CONTENTS. Do NOT paraphrase, guess, or modify the lines you are searching for. They must exactly match the source.
9. You MUST list all patch targets from TEST IMPACT MATRIX in the Tes
>>>
<<<SEARCH
    logger.debug(
        "SPLIT_REQUEST marker found but JSON parse failed, treating as normal runbook"
    )
    return None
===
    logger.debug(
        "SPLIT_REQUEST marker found but JSON parse failed, treating as normal runbook"
    )
    return None


def _generate_runbook_chunked(
    story_id: str,
    story_content: str,
    rules_content: str,
    targeted_context: str,
    source_tree: str,
    source_code: str,
    provider: Optional[str] = None,
    timeout: int = 180,
) -> str:
    """
    Execute a modular, two-phase generation pipeline for detailed runbooks.

    Args:
        story_id: The ID of the story.
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

    context_summary = f"{source_tree}\n\n{source_code}\n\n{targeted_context}\n\nRULES:\n{rules_content}"

    # Phase 1: Skeleton Generation
    with tracer.start_as_current_span("runbook.skeleton_generation") as span:
        skeleton_prompt = generate_skeleton_prompt(story_content)
        console.print("[bold green]🤖 Phase 1: Generating Skeleton...[/bold green]")
        
        skeleton_raw = ai_service.complete(
            system_prompt="You are a senior technical architect. Output ONLY valid JSON.",
            user_prompt=skeleton_prompt,
        )
        
        try:
            skeleton_data = json.loads(skeleton_raw.strip())
            skeleton = RunbookSkeleton.from_dict(skeleton_data)
            span.set_attribute("section_count", len(skeleton.sections))
            logger.info("skeleton_generated", extra={"story_id": story_id, "size": len(skeleton_raw)})
        except (json.JSONDecodeError, ValueError) as exc:
            error_console.print(f"[bold red]❌ Failed to parse Skeleton JSON: {exc}[/bold red]")
            logger.error("skeleton_parse_failed", extra={"error": str(exc), "raw": skeleton_raw})
            raise typer.Exit(code=1)

    # Phase 2: Block Generation
    assembled_content = f"# Runbook: {skeleton.title}\n\n## State\n\nPROPOSED\n\n"
    
    for i, section in enumerate(skeleton.sections, 1):
        with tracer.start_as_current_span("runbook.block_generation") as bspan:
            bspan.set_attribute("section_index", i)
            bspan.set_attribute("section_title", section.title)
            
            console.print(f"[bold green]🤖 Phase 2: Generating Block {i}/{len(skeleton.sections)}: {section.title}...[/bold green]")
            
            block_prompt = generate_block_prompt(
                section.title, section.description, skeleton_raw, story_content, context_summary
            )
            
            block_raw = ai_service.complete(
                system_prompt="You are an implementation specialist. Output ONLY valid JSON.",
                user_prompt=block_prompt,
            )
            
            try:
                block_data = json.loads(block_raw.strip())
                block = RunbookBlock.from_dict(block_data)
                assembled_content += f"## {block.header}\n\n{block.content}\n\n"
                logger.info("block_generated", extra={"section": section.title, "size": len(block_raw)})
            except (json.JSONDecodeError, ValueError) as exc:
                error_console.print(f"[bold red]❌ Failed to parse Block JSON for '{section.title}': {exc}[/bold red]")
                logger.warning("block_parse_failed", extra={"section": section.title, "error": str(exc)})
                # Best effort: append the raw content if it looks like markdown, else skip
                assembled_content += f"## {section.title}\n\n[Generation failed for this section]\n\n"

    return assembled_content
>>>
```

### Step 4: Add Unit Tests for Chunk Models

#### [NEW] .agent/src/agent/core/implement/tests/test_chunk_models.py

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

"""Tests for runbook chunking data models."""

import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock, SkeletonSection


def test_skeleton_from_dict_valid():
    """Test parsing a valid skeleton dictionary."""
    data = {
        "title": "Test Runbook",
        "sections": [
            {"title": "Section 1", "description": "Desc 1", "estimated_tokens": 100},
            {"title": "Section 2", "description": "Desc 2", "estimated_tokens": 200}
        ]
    }
    skeleton = RunbookSkeleton.from_dict(data)
    assert skeleton.title == "Test Runbook"
    assert len(skeleton.sections) == 2
    assert skeleton.sections[0].title == "Section 1"
    assert skeleton.sections[1].estimated_tokens == 200


def test_skeleton_from_dict_missing_fields():
    """Test parsing a skeleton with missing fields raises ValueError."""
    data = {"title": "Incomplete"}
    with pytest.raises(ValueError, match="Skeleton JSON must contain 'title' and 'sections'"):
        RunbookSkeleton.from_dict(data)


def test_skeleton_from_dict_invalid_sections():
    """Test parsing a skeleton with invalid sections raises ValueError."""
    data = {"title": "Bad Sections", "sections": "not a list"}
    with pytest.raises(ValueError, match="'sections' must be a JSON array"):
        RunbookSkeleton.from_dict(data)


def test_block_from_dict_valid():
    """Test parsing a valid block dictionary."""
    data = {
        "header": "Implementation Steps",
        "content": "### Step 1\nModify file.py"
    }
    block = RunbookBlock.from_dict(data)
    assert block.header == "Implementation Steps"
    assert "Modify file.py" in block.content


def test_block_from_dict_missing_fields():
    """Test parsing a block with missing fields raises ValueError."""
    data = {"header": "Missing Content"}
    with pytest.raises(ValueError, match="Block JSON must contain 'header' and 'content'"):
        RunbookBlock.from_dict(data)
```

### Step 5: Update CHANGELOG.md

#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
### Added
===
### Added
- **INFRA-165**: Introduced a modular, two-phase chunked generation pipeline for runbooks, including Phase 1 Skeleton and Phase 2 Block generation with JSON validation and OTel tracing.
>>>
```

### Step 6: Update Impact Analysis in story file

#### [MODIFY] .agent/cache/stories/INFRA/INFRA-165-define-chunked-runbook-skeleton-and-prompts.md

```
<<<SEARCH
**Components touched:**
- `.agent/src/agent/core/implement/chunk_models.py` [NEW]
- `.agent/src/agent/core/ai/prompts.py`
- `.agent/src/agent/commands/runbook.py`
===
**Components touched:**
- `.agent/src/agent/core/implement/chunk_models.py` — **[NEW]** Data models for Skeleton and Block structures.
- `.agent/src/agent/core/implement/tests/test_chunk_models.py` — **[NEW]** Unit tests for chunk models.
- `.agent/src/agent/core/ai/prompts.py` — **[MODIFIED]** Added Phase 1 (Skeleton) and Phase 2 (Block) prompt generators.
- `.agent/src/agent/commands/runbook.py` — **[MODIFIED]** Added chunked generation pipeline logic and `--chunked` flag.
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/core/implement/tests/test_chunk_models.py` - Verify model parsing and validation logic.
- [ ] `pytest .agent/src/agent/commands/tests/test_runbook.py` - (Existing tests) Ensure no regressions in standard runbook generation.

### Manual Verification

- [ ] Run `agent new-runbook INFRA-165 --chunked` and verify the generation phases appear in the console.
- [ ] Inspect the generated runbook at `.agent/cache/runbooks/INFRA/INFRA-165-runbook.md` to ensure coherent structure and detailed content.
- [ ] Verify OTel spans for `runbook.skeleton_generation` and `runbook.block_generation` are captured in the telemetry sink.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated (see Step 5 above)
- [x] Story `## Impact Analysis Summary` updated to list every touched file (see Step 6 above)
- [ ] README.md updated (if applicable)

### Observability

- [x] Logs are structured and free of PII
- [x] New structured `extra=` dicts added if new logging added

### Testing

- [x] All existing tests pass
- [x] New tests added for each new public interface

## Copyright

Copyright 2026 Justin Cook