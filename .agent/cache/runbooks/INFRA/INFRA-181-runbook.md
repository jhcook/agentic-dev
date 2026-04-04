# Runbook: Implementation Runbook for INFRA-181

## State

PROPOSED

## Implementation Steps

### Step 1: Architecture & Design Review

Define the Pydantic schema for structured runbook operations to ensure strict typing and validation of LLM-generated code blocks.

**Design Objectives**
- **Validation (AC-2)**: Leverage Pydantic's validation engine to enforce that 'modify' operations include both search and replace strings, while 'new' operations provide the full content string.
- **Schema Enforcement**: Provide a discrete contract for the Phase 2 generation prompt (AC-1), moving away from bespoke markdown delimiters in LLM output.
- **Backward Compatibility**: Ensure the data structure can be serialized back into the existing `<<<SEARCH/===/>>>` format (AC-3).

#### [NEW] .agent/src/agent/core/models/runbook.py

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

"""Models for structured runbook generation operations."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class RunbookOpJson(BaseModel):
    """
    Structured representation of a file operation in a generated runbook.

    This model is used to validate JSON output from the LLM before it is
    assembled into the final markdown format with delimiters.
    """

    op: Literal["modify", "new", "delete"] = Field(
        ..., description="The type of operation to perform."
    )
    file: str = Field(
        ..., description="The repository-relative path to the target file."
    )
    search: Optional[str] = Field(
        None, description="The exact text to find in the file. Required for 'modify'."
    )
    replace: Optional[str] = Field(
        None, description="The text to replace the search block with. Required for 'modify'."
    )
    content: Optional[str] = Field(
        None, description="The full content of the file. Required for 'new'."
    )
    rationale: Optional[str] = Field(
        None, description="The reason for deletion. Required for 'delete'."
    )

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> "RunbookOpJson":
        """Verify that required fields are present for specific operation types."""
        if self.op == "modify":
            if self.search is None or self.replace is None:
                raise ValueError(
                    "Operations with op='modify' must provide both 'search' and 'replace' fields."
                )
        elif self.op == "new":
            if self.content is None:
                raise ValueError(
                    "Operations with op='new' must provide the 'content' field."
                )
        elif self.op == "delete":
            if self.rationale is None:
                raise ValueError(
                    "Operations with op='delete' must provide the 'rationale' field."
                )
        return self

```

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased]
===
## [Unreleased] (Updated by story)

## [Unreleased]

**Added**
- Pydantic model `RunbookOpJson` in `.agent/src/agent/core/models/runbook.py` for structured generation (INFRA-181).
>>>

```

**Troubleshooting**
- If validation fails during chunk generation, ensure the Phase 2 prompt explicitly identifies all required fields for each `op` type.
- If the LLM generates a JSON array directly (as requested in AC-1), ensure the parsing logic uses `pydantic.TypeAdapter` or iterates through the array to validate each object against `RunbookOpJson`.

### Step 2: Implementation

Refactor the runbook generation pipeline to transition from raw Markdown block generation to structured JSON generation with manual delimiter injection.

#### [MODIFY] .agent/src/agent/commands/runbook_generation.py

```

<<<SEARCH
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
===
@dataclass
class GenerationBlock:
    """A single generated implementation block from Phase 2."""

    header: str
    content: str = ""
    ops: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationBlock":
        """Build from the JSON dict returned by the AI.

        Supports both structured 'ops' array and legacy 'content' string.
        """
        header = data.get("header", data.get("title", "Untitled"))
        if "ops" in data and isinstance(data["ops"], list):
            return cls(header=header, ops=data["ops"])
        return cls(
            header=header,
            content=data.get("content", data.get("body", "")),
        )


def _assemble_block_from_json(block: GenerationBlock) -> str:
    """Assembles implementation markdown from structured JSON operations.

    Injects headers and SEARCH/REPLACE delimiters around raw code content.
    """
    if block.content and not block.ops:
        return block.content

    parts: List[str] = []
    for op in block.ops:
        action = str(op.get("op", "modify")).upper()
        path = op.get("file", "unknown")
        parts.append(f"#### [{action}] {path}")

        if action == "NEW":
            content = op.get("content", op.get("replace", ""))
            # AC-1: Strip inner fences and sanitize
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            # AC-6: sanitize backticks inside code values to prevent markdown breakage
            content = content.replace("```", "'''")
            parts.append(f"```\n{content}\n```")
        elif action == "MODIFY":
            search = op.get("search", "")
            replace = op.get("replace", "")
            parts.append(f"```\n<<<SEARCH\n{search}\n===\n{replace}\n>>>\n```")
        elif action == "DELETE":
            parts.append(f"Rationale: {op.get('rationale', 'File no longer needed.')}")
        parts.append("")

    return "\n".join(parts).strip()
>>>
<<<SEARCH
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
===
>>>
<<<SEARCH
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
===
>>>
<<<SEARCH
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
===
>>>
<<<SEARCH
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
===
>>>
<<<SEARCH
        block_prompt = generate_block_prompt(
            section.title,
            section.description,
            skeleton_raw,
            story_content,
            context_summary,
            prior_changes=None,  # omitted for parallel; dedup handled in Phase 2c
            modify_file_contents=modify_contents or None,
            existing_files=all_existing_files or None,
        )
===
        # AC-8: Rollback support for legacy markdown generation
        legacy_mode = os.environ.get("RUNBOOK_GENERATION_LEGACY") == "1"

        block_prompt = generate_block_prompt(
            section.title,
            section.description,
            skeleton_raw,
            story_content,
            context_summary,
            prior_changes=None,  # omitted for parallel; dedup handled in Phase 2c
            modify_file_contents=modify_contents or None,
            existing_files=all_existing_files or None,
            legacy=legacy_mode,
        )
>>>
<<<SEARCH
    for _r in _par_results_1:
        if _r["status"] == "success":
            raw_by_step[_r["data"]["step"]] = _r["data"]["raw"]
            try:
                b = GenerationBlock.from_dict(_extract_json(_r["data"]["raw"]))
                pass_1_context.append(f"### {b.header}\n\n{b.content}")
            except Exception: pass
===
    for _r in _par_results_1:
        if _r["status"] == "success":
            raw_by_step[_r["data"]["step"]] = _r["data"]["raw"]
            try:
                b = GenerationBlock.from_dict(_extract_json(_r["data"]["raw"]))
                # Assemble content for context of subsequent Pass 2 blocks
                b_content = b.content if b.content else _assemble_block_from_json(b)
                pass_1_context.append(f"### {b.header}\n\n{b_content}")
            except Exception: pass
>>>
<<<SEARCH
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
===
                        # AC-5: Retry: re-prompt the AI with the specific schema feedback.
                        block_raw = ai_service.complete(
                            system_prompt=(
                                "You are an implementation specialist. Output ONLY valid JSON. "
                                "Your previous response had a JSON schema or syntax error: "
                                f"{exc}. "
                                "Ensure all strings are properly escaped. Do NOT wrap your "
                                "response in markdown fences. Structure: {'header': str, "
                                "'ops': [{'file': str, 'op': 'modify'|'new'|'delete', "
                                "'search'?: str, 'replace'?: str, 'content'?: str}]}"
                            ),
                            user_prompt=_prompt,
                        )


            if parse_ok:
                # AC-1, AC-3: Assemble implementation markdown from structured JSON
                cleaned = _assemble_block_from_json(block)

                # demote any remaining ### sub-headers in block narrative to **bold**
                def _demote(m: re.Match) -> str:
                    txt = m.group(1).strip()
                    if re.match(r'^Step \d+', txt): return m.group(0)
                    return f'**{txt}**'

                cleaned = re.sub(r'^### (.+)$', _demote, cleaned, flags=re.MULTILINE)

                # Blank line before code fences (prevents markdownlint failures)
                cleaned = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', cleaned)

                # Deterministic duplicate-file strip remains as a safety net
                if prior_changes:
>>>
<<<SEARCH
                # Auto-fence: ensure [NEW] blocks have fenced code content
                cleaned = _ensure_new_blocks_fenced(cleaned)
                cleaned = _ensure_modify_blocks_fenced(cleaned)
===
                # Auto-fencing is now handled by _assemble_block_from_json delimiter injection
>>>
<<<SEARCH
                logger.info(
                    "block_generated",
                    extra={
                        "section": section.title,
                        "size": len(block_raw),
                        "files_touched": len(file_blocks),
                        "total_prior_files": len(prior_changes),
                    },
                )
===
                logger.info(
                    "block_generated",
                    extra={
                        "section": section.title,
                        "size": len(block_raw),
                        "op_count": len(block.ops) if block.ops else len(file_blocks),
                        "retry_count": attempt,
                        "model": _model_hint,
                        "total_prior_files": len(prior_changes),
                    },
                )
>>>
<<<SEARCH
    # Post-generation passes (order matters)
    assembled_content = _ensure_modify_blocks_fenced(assembled_content)
    assembled_content = _dedup_modify_blocks(assembled_content)
    assembled_content = _escape_dunder_paths(assembled_content)
    # Deterministic fence balancer: close any orphaned fences per Step block.
    # This is a pipeline guarantee — the LLM is not trusted to balance fences.
    assembled_content = _rebalance_fences(assembled_content)
    # Normalise list markers: * → -, double-space → single-space (MD004/MD030)
    assembled_content = _normalize_list_markers(assembled_content)
    # Rewrite # Changelog in S/R SEARCH blocks to avoid MD024/MD025
    assembled_content = _fix_changelog_sr_headings(assembled_content)
    # Ensure blank lines surround fenced blocks (MD031)
    assembled_content = _ensure_blank_lines_around_fences(assembled_content)
===
    # Post-generation passes (order matters)
    assembled_content = _dedup_modify_blocks(assembled_content)
    assembled_content = _escape_dunder_paths(assembled_content)
    # Normalise list markers: * → -, double-space → single-space (MD004/MD030)
    assembled_content = _normalize_list_markers(assembled_content)
    # Ensure blank lines surround fenced blocks (MD031)
    assembled_content = _ensure_blank_lines_around_fences(assembled_content)
>>>

```

### Step 3: Security & Input Sanitization

Implement recursive JSON value sanitization to ensure that LLM-generated code content does not contain redundant markdown fences that would break the final runbook assembly. This layer of defense prevents the "nested fence" problem where an AI-generated string value like `"```python\ncode\n```"` is wrapped in another set of triple-backticks by the Python assembler, resulting in invalid markdown. This section also ensures that `json.loads` is used as the exclusive parsing mechanism (avoiding unsafe alternatives like `eval`).



### Step 4: Observability & Audit Logging

Integrate structured logging into the Phase 2 chunk generation loop to track pipeline reliability and performance. This update enhances the `block_generated` event by including `op_count` (the number of search/replace or new-file operations in the chunk), `retry_count` (the number of parse/validation retries triggered), and the `model` identifier, following the standards defined in ADR-046.

#### [MODIFY/NEW]` blocks assembled from the JSON. If this differs from the number of objects in the LLM's JSON array, check for deduplication logic in the assembler.

### Step 5: Verification & Test Suite

Implement a comprehensive unit test suite to verify the structured JSON generation pipeline. This suite validates the transformation from raw LLM JSON output to the serialized markdown format required by the implementation engine, ensuring that delimiters are correctly injected and inputs are sanitized to prevent markdown corruption.

**Test Objectives**
- **Assembly Correctness (AC-1, AC-3)**: Confirm that 'modify' operations result in `<<<SEARCH/===/>>>` blocks and 'new' operations create `#### [NEW]` headers with appropriate code fences.
- **Schema Enforcement (AC-2, AC-5)**: Verify that the `RunbookOpJson` model correctly identifies missing fields (e.g., missing 'search' in a modify op) which triggers the retry logic.
- **Input Sanitization (AC-6)**: Validate that `_sanitize_json_values` recursively removes redundant triple-backticks from LLM responses and that `_assemble_block_from_json` handles inner backticks safely.
- **Robust Extraction**: Ensure the balanced-brace logic correctly extracts JSON from responses containing conversational prose.

#### [NEW] .agent/tests/agent/commands/test_runbook_generation_json.py

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

"""Unit tests for structured JSON runbook generation (INFRA-181)."""

import pytest
import json
from agent.commands.runbook_generation import (
    GenerationBlock,
    _assemble_block_from_json,
    _sanitize_json_values,
    _extract_json
)
from agent.core.models.runbook import RunbookOpJson

def test_assemble_modify_block_from_json():
    """Verify that a 'modify' operation correctly injects SEARCH/REPLACE delimiters (AC-1)."""
    ops = [{
        "op": "modify",
        "file": ".agent/src/agent/core/utils.py",
        "search": "def old_func():\n    return True",
        "replace": "def new_func():\n    return False"
    }]
    block = GenerationBlock(header="Refactor Utils", ops=ops)
    assembled = _assemble_block_from_json(block)
    
    assert "#### [MODIFY] .agent/src/agent/core/utils.py" in assembled
    assert "<<<SEARCH\ndef old_func():\n    return True\n===\ndef new_func():\n    return False\n>>>" in assembled

def test_assemble_new_block_from_json():
    """Verify that a 'new' operation correctly wraps content in code fences (AC-3)."""
    ops = [{
        "op": "new",
        "file": ".agent/src/agent/core/models/new_model.py",
        "content": "class NewModel: pass"
    }]
    block = GenerationBlock(header="Create Model", ops=ops)
    assembled = _assemble_block_from_json(block)
    
    assert "#### [NEW] .agent/src/agent/core/models/new_model.py" in assembled
    assert "```\nclass NewModel: pass\n```" in assembled

def test_json_value_sanitization_recursive():
    """Verify that nested markdown fences are stripped from JSON values (AC-6)."""
    # Test strings with leading/trailing markdown fences often emitted by LLMs
    raw_json = {
        "header": "Test",
        "ops": [
            {"op": "new", "file": "t.py", "content": "```python\nprint('hello')\n```"}
        ]
    }
    sanitized = _sanitize_json_values(raw_json)
    assert sanitized["ops"][0]["content"] == "print('hello')"

def test_assemble_strips_inner_triple_backticks():
    """Verify that backticks inside content strings are handled to prevent markdown breakage."""
    ops = [{
        "op": "new",
        "file": "README.md",
        "content": "This is a code block: ```python\npass\n```"
    }]
    block = GenerationBlock(header="Update README", ops=ops)
    assembled = _assemble_block_from_json(block)
    
    # The Pass 2 implementation replaces inner backticks with single quotes to preserve text
    # while ensuring the outer markdown fence of the implementation block remains valid.
    assert "This is a code block: '''python\npass\n'''" in assembled
    assert assembled.count("```") == 2 # Only the outer injection fences

def test_schema_validation_modify_missing_fields():
    """AC-2: Verify that missing fields in 'modify' ops raise validation errors for retries."""
    # Missing 'replace'
    with pytest.raises(ValueError, match="must provide both 'search' and 'replace'"):
        RunbookOpJson(op="modify", file="f.py", search="old")
    
    # Missing 'search'
    with pytest.raises(ValueError, match="must provide both 'search' and 'replace'"):
        RunbookOpJson(op="modify", file="f.py", replace="new")

def test_extract_json_balanced_extraction():
    """Confirm that JSON can be extracted from LLM responses containing conversational text."""
    mixed_response = (
        "Certainly! Here are the operations in JSON format:\n\n"
        "```json\n"
        "{\"header\": \"Update\", \"ops\": [{\"op\": \"delete\", \"file\": \"old.py\", \"rationale\": \"deprecated\"}]}\n"
        "```\n\n"
        "Let me know if you need anything else."
    )
    extracted = _extract_json(mixed_response)
    assert extracted["header"] == "Update"
    assert extracted["ops"][0]["file"] == "old.py"

```



### Step 6: Deployment & Rollback Strategy

**Deployment Verification**

The structured JSON output mechanism for runbook generation is deployed alongside a legacy safety switch. This section outlines the verification process for the rollback mechanism, ensuring that the system can revert to the previous markdown-delimited prompt templates via environment variable configuration without requiring code changes or redeployments.

**Verification Procedure**

1. **Legacy Toggle Test**: Set the environment variable `RUNBOOK_GENERATION_LEGACY=1` in the local execution environment.
2. **Execution**: Run the runbook generation command for a test story: `agent new-runbook INFRA-ROLLBACK-VERIFY --dry-run`.
3. **Prompt Inspection**: Verify through debug logs or telemetry that the Phase 2 prompt construction uses the legacy markdown templates (containing instructions for `#### [MODIFY]` and `<<<SEARCH` delimiters) instead of the new JSON schema instructions.
4. **Bypass Validation**: Confirm that `_assemble_block_from_json` is bypassed and the `block_generated` observability event (defined in Sec 4) is NOT emitted, as the legacy path does not produce structured operation counts.
5. **Recovery**: Unset the environment variable and confirm the generator returns to structured JSON mode.

**Rollback Procedure**

If Phase 2 generation produces consistent JSON parsing errors or schema violations that block implementation workflows:
-   Set `RUNBOOK_GENERATION_LEGACY=1` in the production environment settings.
-   This immediately restores the prompt-based delimiter generation used prior to INFRA-181 while maintaining compatibility with all existing implementation gates.



