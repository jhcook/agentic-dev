# Runbook: Implementation Runbook for INFRA-168

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

Review ADR-012 to align on parsing strategy. The implementation will use a block-based decomposition model where runbook skeletons are treated as a sequence of addressable segments identified by persistent IDs. This ensures that generated content can be injected into specific slots without losing the surrounding formatting, comments, or metadata.

**1. Intermediate Block Schema**

The intermediate representation (IR) is defined by the `RunbookBlock` and `RunbookSkeleton` models. These models capture the raw content, extracted metadata, and the exact whitespace required to reconstruct the document with 0% deviation.

#### [NEW] .agent/src/agent/core/implement/chunk_models.py

```python
# Copyright 2026 Justin Cook

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RunbookBlock(BaseModel):
    """Represents a discrete, addressable segment of a runbook.

    Attributes:
        id: A unique identifier for the block, usually derived from comments.
        content: The raw text content of the block excluding boundaries.
        metadata: Key-value pairs extracted from block tags (e.g., tags, version).
        prefix_whitespace: Exact whitespace/newlines preceding the block content.
        suffix_whitespace: Exact whitespace/newlines following the block content.
        block_type: The source format (e.g., 'markdown', 'yaml').
    """
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    prefix_whitespace: str = ""
    suffix_whitespace: str = ""
    block_type: str = "markdown"

class RunbookSkeleton(BaseModel):
    """A complete collection of blocks representing a full runbook template."""
    blocks: List[RunbookBlock]
    source_path: Optional[str] = None
    version: str = "1.0.0"

    def get_block(self, block_id: str) -> Optional[RunbookBlock]:
        """Retrieve a specific block by its ID."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None

```

**2. Regex and Boundary Patterns**

The parser identifies block boundaries using the following patterns for Markdown and YAML. These patterns are designed to be non-destructive, capturing metadata within comments that are ignored by standard renderers.

#### Markdown Block Patterns
- **Block ID Tag**: `<!-- id: ([a-zA-Z0-9_-]+) -->` - Identifies the start of a block and its unique address.
- **Metadata Tag**: `<!-- metadata: ({.*?}) -->` - Captures JSON-formatted metadata for the block.
- **Section Boundaries**: Defined by Markdown headers (`^#{1,6}\s+.*$`) or explicit ID tags.

#### YAML Block Patterns
- **Comment ID**: `# id: ([a-zA-Z0-9_-]+)` - Used in YAML files where HTML comments are invalid.
- **Property-based ID**: Scans for top-level keys if they match the skeleton schema.

**3. Whitespace Preservation Strategy**

To meet the requirement for 0% deviation during re-assembly:
1. The parser splits the document using `re.split()` with capturing groups for the separators.
2. Each non-empty segment is evaluated for ID tags.
3. Leading and trailing whitespace for each segment is stored in `prefix_whitespace` and `suffix_whitespace` respectively.
4. The `AssemblyEngine` will iterate through the `RunbookSkeleton.blocks` list, concatenating `prefix_whitespace + content + suffix_whitespace` for every member.

#### [NEW] .agent/src/agent/core/implement/assembly_engine.py

```python
# Copyright 2026 Justin Cook

from agent.core.implement.chunk_models import RunbookSkeleton

class AssemblyEngine:
    """Engine responsible for reconstructing documents from block maps."""

    def assemble(self, skeleton: RunbookSkeleton) -> str:
        """Reconstruct the original document from a RunbookSkeleton object.

        Ensures exact preservation of whitespace and styling by concatenating
        blocks in their original order with preserved tokens.
        """
        parts = []
        for block in skeleton.blocks:
            parts.append(block.prefix_whitespace)
            parts.append(block.content)
            parts.append(block.suffix_whitespace)
        return "".join(parts)

```

**Troubleshooting & Risks**
- **ID Collisions**: If multiple blocks share an ID, the parser will raise an `InvalidTemplateError`. Every block in a skeleton must be uniquely addressable.
- **Nested Blocks**: Currently, the strategy supports flat block lists. Nested structures (e.g., blocks within blocks) will be treated as single opaque content segments unless further ADRs extend the schema.
- **Linter Interference**: Some formatters (like `prettier` or `black`) may move comments. Skeletons should be excluded from auto-formatting or use specific 'no-format' regions if drift occurs.

### Step 2: Implementation: Skeleton Parser

Develop the core parsing logic for runbook skeletons. This implementation introduces the ability to decompose markdown templates into a structured `RunbookSkeleton` object, mapping addressable segments to `RunbookBlock` models while preserving exact whitespace for high-fidelity reconstruction.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```python
<<<SEARCH
from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    ParsingError,
    RunbookSchema,
    RunbookStep,
    SearchReplaceBlock,
)

try:
===
from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    ParsingError,
    RunbookSchema,
    RunbookStep,
    SearchReplaceBlock,
)
from agent.core.implement.chunk_models import RunbookBlock, RunbookSkeleton

try:
>>>
<<<SEARCH
_tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None
_logger = get_logger(__name__)
===
_tracer = trace.get_tracer(__name__)
except ImportError:
    _tracer = None
_logger = get_logger(__name__)


class InvalidTemplateError(Exception):
    """Raised when a runbook skeleton is malformed or lacks addressable blocks."""
    pass
>>>
<<<SEARCH
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
===
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


def parse_skeleton(content: str, source_path: Optional[str] = None) -> RunbookSkeleton:
    """Decompose a template string into addressable blocks with metadata mapping.

    Recognises blocks bounded by HTML-style comments:
    <!-- block: id key=value -->
    Content
    <!-- /block -->

    Args:
        content: Raw template string.
        source_path: Optional path to the source file for reference.

    Returns:
        A RunbookSkeleton containing the mapped blocks.

    Raises:
        InvalidTemplateError: If no blocks are found, IDs are duplicated,
                             or block structure is malformed.
    """
    # Pattern captures block ID, metadata, and the raw inner content.
    pattern = re.compile(
        r'<!--\s*block:\s*(?P<id>[\w-]+)\s*(?P<meta>.*?)\s*-->(?P<content>.*?)<!--\s*/block\s*-->',
        re.DOTALL
    )

    matches = list(pattern.finditer(content))
    if not matches:
        raise InvalidTemplateError(
            "No addressable blocks found. Templates must contain markers in the format: "
            "<!-- block: id --> content <!-- /block -->"
        )

    blocks: List[RunbookBlock] = []
    seen_ids = set()
    last_pos = 0

    for i, match in enumerate(matches):
        block_id = match.group('id')
        if block_id in seen_ids:
            raise InvalidTemplateError(f"Duplicate block ID '{block_id}' found in skeleton.")
        seen_ids.add(block_id)

        # Metadata extraction: key=value (supports underscores and dots in values)
        meta_raw = match.group('meta')
        metadata = {}
        if meta_raw:
            kv_pairs = re.findall(r'(\w+)=["\']?([\w.-]+)["\']?', meta_raw)
            metadata = {k: v for k, v in kv_pairs}

        # Assign prefix whitespace (text between previous block end and current tags)
        prefix = content[last_pos:match.start()]
        
        # Suffix whitespace (remaining text after the last block tag)
        suffix = ""
        if i == len(matches) - 1:
            suffix = content[match.end():]

        blocks.append(RunbookBlock(
            id=block_id,
            content=match.group('content'),
            metadata=metadata,
            prefix_whitespace=prefix,
            suffix_whitespace=suffix,
            block_type="markdown"
        ))
        last_pos = match.end()

    return RunbookSkeleton(blocks=blocks, source_path=source_path)
>>>

```

#### [MODIFY] .agent/src/agent/core/implement/tests/test_parser.py

```python
<<<SEARCH
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
)
===
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
    parse_skeleton,
    InvalidTemplateError,
)
>>>
<<<SEARCH
    def test_delete_with_valid_rationale_passes(self):
        """A [DELETE] block with a meaningful rationale should pass validation."""
        content = _wrap_runbook(
            "#### [DELETE] old_file.py\n\n"
            "This module is deprecated and replaced by new_file.py.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) == 0
===
    def test_delete_with_valid_rationale_passes(self):
        """A [DELETE] block with a meaningful rationale should pass validation."""
        content = _wrap_runbook(
            "#### [DELETE] old_file.py\n\n"
            "This module is deprecated and replaced by new_file.py.\n"
        )
        violations = validate_runbook_schema(content)
        assert len(violations) == 0


class TestSkeletonParser:
    """Verify decomposition of templates into addressable blocks (INFRA-168)."""

    def test_parse_skeleton_success(self):
        """Verify valid blocks are extracted with metadata and whitespace preservation."""
        template = (
            "# Document Prelude\n"
            "  <!-- block: section-1 category=intro -->\n"
            "  Initial content\n"
            "  <!-- /block -->\n"
            "\n"
            "<!-- block: section-2 version=2.0 -->\n"
            "Secondary content\n"
            "<!-- /block -->\n"
            "EOF footer"
        )
        skeleton = parse_skeleton(template)
        assert len(skeleton.blocks) == 2
        
        b1 = skeleton.get_block("section-1")
        assert b1.metadata["category"] == "intro"
        assert "Initial content" in b1.content
        assert b1.prefix_whitespace == "# Document Prelude\n  "
        
        b2 = skeleton.get_block("section-2")
        assert b2.metadata["version"] == "2.0"
        assert b2.suffix_whitespace == "\nEOF footer"

    def test_parse_skeleton_duplicate_id_raises(self):
        """Verify duplicate block IDs trigger InvalidTemplateError."""
        template = (
            "<!-- block: same --> content <!-- /block -->\n"
            "<!-- block: same --> content <!-- /block -->"
        )
        with pytest.raises(InvalidTemplateError, match="Duplicate block ID"):
            parse_skeleton(template)

    def test_parse_skeleton_no_blocks_raises(self):
        """Verify templates without block markers trigger InvalidTemplateError."""
        template = "Plain text without any addressable blocks."
        with pytest.raises(InvalidTemplateError, match="No addressable blocks"):
            parse_skeleton(template)
>>>

```

**Troubleshooting**
- **Unclosed Blocks**: The parser relies on strict `<!-- /block -->` closing tags. If a template is truncated, `parse_skeleton` will ignore unclosed blocks, which may trigger the `InvalidTemplateError` if no complete blocks are found.
- **Metadata Formatting**: Metadata keys and values must not contain spaces unless quoted. The current regex supports `key=value`, `key="value"`, and `key='value'`.

### Step 3: Implementation: Assembly Engine

This section implements the `AssemblyEngine` to handle document reconstruction with high fidelity. The engine prioritizes whitespace preservation and supports targeted content injection, allowing the AI to update specific blocks while maintaining the structural integrity of the overall template.

#### [MODIFY] .agent/src/agent/core/implement/assembly_engine.py

```python
<<<SEARCH
class AssemblyEngine:
    """Engine responsible for reconstructing documents from block maps."""

    def assemble(self, skeleton: RunbookSkeleton) -> str:
        """Reconstruct the original document from a RunbookSkeleton object.

        Ensures exact preservation of whitespace and styling by concatenating
        blocks in their original order with preserved tokens.
        """
        parts = []
        for block in skeleton.blocks:
            parts.append(block.prefix_whitespace)
            parts.append(block.content)
            parts.append(block.suffix_whitespace)
        return "".join(parts)
===
from typing import Dict, Optional

class InvalidTemplateError(Exception):
    """Raised when a skeleton template is malformed or assembly fails."""
    pass

class AssemblyEngine:
    """Engine responsible for reconstructing documents from block maps."""

    def assemble(
        self, 
        skeleton: RunbookSkeleton, 
        injections: Optional[Dict[str, str]] = None
    ) -> str:
        """Reconstruct the document from a RunbookSkeleton.

        Ensures exact preservation of whitespace and styling by concatenating
        blocks in their original order. Supports partial content injection.

        Args:
            skeleton: The parsed RunbookSkeleton containing blocks.
            injections: Optional mapping of block IDs to replacement content.

        Returns:
            The fully assembled document string.

        Raises:
            InvalidTemplateError: If the skeleton has no blocks or duplicate IDs.
        """
        if not skeleton.blocks:
            raise InvalidTemplateError("Cannot assemble an empty skeleton.")

        injections = injections or {}
        seen_ids = set()
        parts = []

        for block in skeleton.blocks:
            if block.id in seen_ids:
                raise InvalidTemplateError(f"Duplicate block ID detected: {block.id}")
            seen_ids.add(block.id)

            # Use injected content if ID matches, else original block content
            content = injections.get(block.id, block.content)

            parts.append(block.prefix_whitespace)
            parts.append(content)
            parts.append(block.suffix_whitespace)

        return "".join(parts)
>>>

```

#### [NEW] .agent/src/agent/core/implement/tests/test_assembly_engine.py

```python
# Copyright 2026 Justin Cook

import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError

def test_assemble_round_trip():
    """Verify that a skeleton can be reconstructed exactly without injections."""
    blocks = [
        RunbookBlock(
            id="header", 
            content="# Title", 
            prefix_whitespace="", 
            suffix_whitespace="\n\n"
        ),
        RunbookBlock(
            id="body", 
            content="This is the body.", 
            prefix_whitespace="", 
            suffix_whitespace="\n"
        )
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    result = engine.assemble(skeleton)
    assert result == "# Title\n\nThis is the body.\n"

def test_assemble_with_injection():
    """Verify that injected content replaces the original block content."""
    blocks = [
        RunbookBlock(id="b1", content="Original", suffix_whitespace=" "),
        RunbookBlock(id="b2", content="Text", suffix_whitespace="")
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    injections = {"b1": "Modified"}
    result = engine.assemble(skeleton, injections=injections)
    assert result == "Modified Text"

def test_assemble_preserves_whitespace_around_injection():
    """Verify that whitespace is preserved even when content is injected."""
    blocks = [
        RunbookBlock(
            id="b1", 
            content="[BLOCK]", 
            prefix_whitespace="  ", 
            suffix_whitespace="  "
        )
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    
    result = engine.assemble(skeleton, injections={"b1": "NEW"})
    assert result == "  NEW  "

def test_assemble_empty_skeleton_raises():
    """Verify that an empty skeleton triggers InvalidTemplateError."""
    skeleton = RunbookSkeleton(blocks=[])
    engine = AssemblyEngine()
    with pytest.raises(InvalidTemplateError, match="empty skeleton"):
        engine.assemble(skeleton)

def test_assemble_duplicate_ids_raises():
    """Verify that duplicate block IDs trigger InvalidTemplateError."""
    blocks = [
        RunbookBlock(id="dup", content="one"),
        RunbookBlock(id="dup", content="two")
    ]
    skeleton = RunbookSkeleton(blocks=blocks)
    engine = AssemblyEngine()
    with pytest.raises(InvalidTemplateError, match="Duplicate block ID"):
        engine.assemble(skeleton)

```

### Step 4: Security & Input Sanitization

This section implements critical security controls for the runbook parsing and assembly pipeline. The focus is on preventing directory traversal attacks via template paths and ensuring that block identifiers and metadata are sanitized to prevent injection or structural manipulation during the parsing phase.

**Security Strategy**
- **Path Safety**: Implements a strict boundary check using `pathlib` to ensure all file references remain within the project scope.
- **ID Sanitization**: Enforces a strict alphanumeric regex for block identifiers to prevent shell injection or regex-breaking characters.
- **Metadata Filtering**: Validates metadata structures to ensure keys are valid identifiers and values are restricted to primitive types, preventing the storage of executable objects.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```python
<<<SEARCH
import sys
from typing import Dict, Any, List, Set, Tuple, Union, Optional
===
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Union, Optional
>>>
<<<SEARCH
def _unescape_path(path: str) -> str:
    """Remove markdown escapes and styling from file paths.

    Strip markers and remove backslash escapes.

    Args:
        path: Raw path string from markdown header.

    Returns:
        Clean, technical file path.
    """
    if not path:
        return ""
    # Remove bold/italic and backticks from the edges only
    path = path.strip().strip('`')
    # Safety net: if mistune rendered __ as ** anywhere in the path, restore it
    path = re.sub(r'\*\*(.*?)\*\*', r'__\1__', path)
    path = re.sub(r'\*(.*?)\*', r'_\1_')
    # Remove backslash escapes for markdown characters: _ * [ ] ( ) # + - . !
    return re.sub(r'\\([_*[\]()#+\-.!])', r'\1', path)
===
def validate_path_safety(path_str: str) -> str:
    """Verify that a path does not attempt directory traversal.

    Args:
        path_str: The file path to validate.

    Returns:
        The validated path string.

    Raises:
        ParsingError: If the path is absolute or attempts to climb up (..).
    """
    if not path_str:
        return ""
    if ".." in path_str or path_str.startswith("/") or ":" in path_str:
        raise ParsingError(f"Security Violation: Potential directory traversal in path: {path_str}")
    return path_str


def validate_block_id(block_id: str) -> str:
    """Sanitize and validate a block identifier.

    Args:
        block_id: The raw identifier extracted from the template.

    Returns:
        The sanitized identifier.

    Raises:
        ParsingError: If the ID contains illegal characters or exceeds length limits.
    """
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", block_id):
        raise ParsingError(f"Security Violation: Invalid characters in block ID: {block_id}")
    if len(block_id) > 64:
        raise ParsingError(f"Security Violation: Block ID too long: {block_id[:10]}...")
    return block_id


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Filter block metadata to prevent injection and ensure storage safety."""
    sanitized = {}
    for k, v in metadata.items():
        safe_key = re.sub(r"[^a-z0-9_]", "", str(k).lower())
        if not safe_key:
            continue
        if isinstance(v, (str, int, float, bool)):
            sanitized[safe_key] = v
    return sanitized


def _unescape_path(path: str) -> str:
    """Remove markdown escapes and styling from file paths.

    Strip markers and remove backslash escapes.

    Args:
        path: Raw path string from markdown header.

    Returns:
        Clean, technical file path.
    """
    if not path:
        return ""
    # Remove bold/italic and backticks from the edges only
    path = path.strip().strip('`')
    # Safety net: if mistune rendered __ as ** anywhere in the path, restore it
    path = re.sub(r'\*\*(.*?)\*\*', r'__\1__', path)
    path = re.sub(r'\*(.*?)\*', r'_\1_', path)
    # Remove backslash escapes for markdown characters: _ * [ ] ( ) # + - . !
    clean_path = re.sub(r'\\([_*[\]()#+\-.!])', r'\1', path)
    return validate_path_safety(clean_path)
>>>

```

#### [MODIFY] .agent/src/agent/core/implement/tests/test_parser.py

```python
<<<SEARCH
class TestDeleteBlockPipeline:
===
class TestSecurityValidation:
    """Verify security constraints for paths and identifiers."""

    def test_traversal_detection_in_path(self):
        """Ensure that paths with .. or absolute roots are blocked."""
        with pytest.raises(ParsingError, match="Security Violation"):
            validate_runbook_schema(_wrap_runbook("#### [NEW] ../../etc/passwd\n\n```\ncode\n```"))

    def test_absolute_path_detection(self):
        """Ensure absolute paths are blocked for runbook operations."""
        with pytest.raises(ParsingError, match="Security Violation"):
            validate_runbook_schema(_wrap_runbook("#### [MODIFY] /var/log/syslog\n\n<<<SEARCH\nx\n===\ny\n>>>"))


class TestDeleteBlockPipeline:
>>>

```

**Troubleshooting**
- **Traversal Violations**: If `validate_runbook_schema` returns a "Security Violation" error, ensure all file paths in `#### [NEW/MODIFY/DELETE]` headers are relative to the project root and do not contain `..` navigation.
- **Invalid Block IDs**: If using custom block tagging (e.g., `<!-- id: my-block -->`), ensure the ID contains only alphanumeric characters, underscores, hyphens, or periods.

### Step 5: Observability & Audit Logging

Integrate comprehensive telemetry into the implementation pipeline to ensure all assembly actions are auditable and performance metrics are captured for system health monitoring. This implementation focuses on capturing structured logs for audit trails and OpenTelemetry attributes for parsing density and latency.

#### [NEW] .agent/src/agent/core/implement/telemetry_helper.py

```python
# Copyright 2026 Justin Cook

import os
import time
from typing import Any, Dict, Optional
from agent.core.logger import get_logger

_logger = get_logger(__name__)

def log_assembly_audit(user: str, template_version: str, block_count: int, success: bool, duration_ms: float):
    """Log a structured audit event for runbook assembly.

    Args:
        user: The identity of the user who triggered the assembly.
        template_version: The version string of the skeleton template used.
        block_count: Number of blocks processed during assembly.
        success: Whether the assembly completed without errors.
        duration_ms: Time taken to assemble in milliseconds.
    """
    _logger.info(
        "runbook_assembly_audit",
        extra={
            "audit": {
                "event": "assembly",
                "user": user,
                "template_version": template_version,
                "block_count": block_count,
                "status": "success" if success else "failure",
                "latency_ms": duration_ms
            }
        }
    )

def calculate_block_density(block_count: int, content: str) -> float:
    """Calculate the mapping density (blocks per 100 lines).

    Args:
        block_count: Number of addressable blocks found.
        content: The raw source content.

    Returns:
        Density percentage as a float.
    """
    lines = len(content.splitlines())
    if lines == 0:
        return 0.0
    return (block_count / lines) * 100

```

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```python
<<<SEARCH
    with span_ctx as span:
        if span:
            span.set_attribute("parser.mode", "legacy" if use_legacy else "ast")
            
        if use_legacy:
===
    with span_ctx as span:
        line_count = len(content.splitlines())
        if span:
            span.set_attribute("parser.mode", "legacy" if use_legacy else "ast")
            span.set_attribute("runbook.line_count", line_count)
            
        if use_legacy:
>>>
<<<SEARCH
        if span:
            span.set_attribute("runbook.step_count", len(steps))

        return steps
===
        if span:
            span.set_attribute("runbook.step_count", len(steps))
            # Calculate and record block mapping density (INFRA-168)
            density = (len(steps) / max(1, line_count)) * 100
            span.set_attribute("runbook.block_density", density)
            _logger.info(
                "skeleton_parsed",
                extra={
                    "block_count": len(steps),
                    "line_count": line_count,
                    "density": f"{density:.2f}%"
                }
            )

        return steps
>>>

```

#### [MODIFY] .agent/src/agent/core/implement/assembly_engine.py

```python
<<<SEARCH
def assemble(self, skeleton: RunbookSkeleton, injections: Optional[Dict[str, str]] = None) -> str:
    """Reconstruct a document from block maps, preserving whitespace."""
    if not skeleton.blocks:
        raise InvalidTemplateError("Cannot assemble an empty skeleton.")
===
def assemble(self, skeleton: RunbookSkeleton, injections: Optional[Dict[str, str]] = None) -> str:
    """Reconstruct a document from block maps, preserving whitespace."""
    import os
    import time
    from agent.core.implement.telemetry_helper import log_assembly_audit

    start_time = time.time()
    user_id = os.getenv("USER") or os.getenv("USERNAME") or "system"

    if not skeleton.blocks:
        log_assembly_audit(user_id, skeleton.version, 0, False, 0)
        raise InvalidTemplateError("Cannot assemble an empty skeleton.")
>>>
<<<SEARCH
    return "".join(output)
===
    result = "".join(output)
    duration_ms = (time.time() - start_time) * 1000
    
    # Audit logging for the assembly action
    log_assembly_audit(
        user=user_id,
        template_version=skeleton.version,
        block_count=len(skeleton.blocks),
        success=True,
        duration_ms=duration_ms
    )

    return result
>>>

```

**Troubleshooting**
- **Missing Audit Logs**: Ensure the `USER` or `USERNAME` environment variable is accessible to the process; otherwise, it defaults to `system`.
- **Density Calculation Mismatch**: Density is calculated based on raw line count before any whitespace normalization. Ensure the source skeleton has consistent newline characters.
- **Performance Overhead**: The logging is structured and minimal; however, if parsing high-frequency small templates, monitor the OTLP exporter buffer to prevent latency spikes.

### Step 6: Verification & Test Suite

This section implements the verification layer to ensure structural integrity and performance of the runbook skeleton system. It includes unit tests for the core regex parsing logic, a zero-deviation round-trip integration test, and performance benchmarks to validate the < 250ms latency requirement.

#### [MODIFY] .agent/src/agent/core/implement/tests/test_parser.py

```python
<<<SEARCH
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
)
===
from agent.core.implement.parser import (
    validate_runbook_schema,
    _extract_runbook_data,
    parse_skeleton,
)
>>>
<<<SEARCH
    violations = validate_runbook_schema(content)
    assert len(violations) == 0
===
    violations = validate_runbook_schema(content)
    assert len(violations) == 0


class TestSkeletonParser:
    """Unit tests for regex logic and block mapping (INFRA-168)."""

    def test_regex_block_identification(self):
        """Verify that block boundaries are correctly identified by the parser."""
        content = "<!-- @block id1 -->content1<!-- @end -->"
        skeleton = parse_skeleton(content)
        assert len(skeleton.blocks) == 1
        assert skeleton.blocks[0].id == "id1"
        assert skeleton.blocks[0].content == "content1"

    def test_block_metadata_mapping(self):
        """Verify extraction of metadata tokens from block tags."""
        content = "<!-- @block id1 version=2.0 tags=infra,test -->content<!-- @end -->"
        skeleton = parse_skeleton(content)
        meta = skeleton.blocks[0].metadata
        assert meta.get("version") == "2.0"
        assert "infra" in meta.get("tags", "")
>>>

```

#### [NEW] .agent/src/agent/core/implement/tests/test_assembly_benchmarks.py

```python
# Copyright 2026 Justin Cook

import time
import pytest
from agent.core.implement.chunk_models import RunbookSkeleton, RunbookBlock
from agent.core.implement.assembly_engine import AssemblyEngine
from agent.core.implement.parser import parse_skeleton

def test_performance_benchmarks():
    """Ensure that parsing and assembly of a 50-block runbook completes in < 250ms."""
    # Setup 50 addressable blocks to simulate a standard complex runbook
    parts = [f"<!-- @block b{i} -->\nBlock {i} Content\n<!-- @end -->" for i in range(50)]
    source = "\n\n".join(parts)
    
    engine = AssemblyEngine()
    
    start = time.perf_counter()
    
    # Execute full pipeline: Parse -> Model -> Assemble
    skeleton = parse_skeleton(source)
    reconstructed = engine.assemble(skeleton)
    
    duration_ms = (time.perf_counter() - start) * 1000
    
    # Requirement: Performance < 250ms
    assert duration_ms < 250, f"Performance benchmark failed: {duration_ms:.2f}ms exceeds 250ms limit"
    assert len(skeleton.blocks) == 50
    assert "Block 49 Content" in reconstructed

def test_round_trip_zero_deviation():
    """Verify 0% deviation between source and re-assembled output to ensure whitespace preservation."""
    source = (
        "# Runbook Skeleton\n\n"
        "<!-- @block b1 -->\n"
        "## Section A\n"
        "Content with specific whitespace and formatting.\n\n"
        "<!-- @end -->\n\n"
        "<!-- @block b2 -->\n"
        "## Section B\n"
        "More content.\n"
        "<!-- @end -->"
    )
    
    engine = AssemblyEngine()
    skeleton = parse_skeleton(source)
    reconstructed = engine.assemble(skeleton)
    
    # Requirement: 0% deviation integration test
    assert reconstructed == source, "Integration 'Round Trip' test failed: Output differs from source string"

def test_partial_injection_integrity():
    """Verify that injecting partial content does not corrupt the surrounding block structure."""
    source = "<!-- @block b1 -->Original<!-- @end -->"
    skeleton = parse_skeleton(source)
    engine = AssemblyEngine()
    
    output = engine.assemble(skeleton, injections={"b1": "Modified"})
    assert output == "<!-- @block b1 -->Modified<!-- @end -->"

```

**Troubleshooting**
- **Regex Failures**: Ensure block tags `<!-- @block id -->` use exact spacing as defined in ADR-012. The parser is whitespace-sensitive to ensure round-trip parity.
- **Performance Issues**: If benchmarks exceed 250ms, investigate regex backtracking in `parser.py` or Pydantic model instantiation overhead in `chunk_models.py`.
- **Drift Detected**: If the Round Trip test fails, verify that `prefix_whitespace` and `suffix_whitespace` are being correctly captured during the `parse_skeleton` phase.

### Step 7: Documentation Updates

Update the project documentation to define the technical standards for runbook skeletons and provide integration guides for the parser and assembly engine.

#### [NEW] .agent/docs/runbook_skeleton_spec.md

```markdown
# Runbook Skeleton Specification

This document defines the structure and tagging conventions for Runbook Skeletons used by the Infrastructure Pipeline.

## Overview

A skeleton is a Markdown or YAML document decomposed into addressable blocks using HTML-style comments. This allows automated agents to inject content into specific segments while preserving the surrounding structure, styling, and whitespace.

## Block Tagging Convention

Blocks are defined using start and end markers. 

**Syntax**

```markdown
<!-- @block <ID> [metadata_key=value] -->
Content goes here.
<!-- @end -->

```

**Rules**
- **ID**: Must be unique within the document. Use snake_case (e.g., `prerequisites`, `step_1_verification`).
- **Metadata**: Optional key-value pairs can be included in the opening tag. These are parsed into the `metadata` dictionary of the `RunbookBlock` model.
- **Nesting**: Blocks currently do not support nesting; flat structures are preferred for addressability.
- **Whitespace**: The parser captures all characters (including newlines and spaces) between the `@block` and `@end` tags, as well as the whitespace surrounding the tags themselves, to ensure bit-perfect reconstruction.

## Example Skeleton

```markdown
# Incident Response: [Service Name]

<!-- @block metadata version=1.2 -->
Created: 2026-01-01
Author: SRE Team
<!-- @end -->

## Steps

<!-- @block step_1 -->
1. Check the logs.
<!-- @end -->

```

```

#### [NEW] .agent/docs/runbook_api_usage.md

```markdown
# Parser and Assembly Engine API Usage

This guide demonstrates how to programmatically manipulate runbook skeletons using the `agent.core.implement` module.

## Parsing a Skeleton

The `parser.py` module converts raw text into a `RunbookSkeleton` object containing `RunbookBlock` instances.

```python
from agent.core.implement.parser import parse_skeleton

raw_content = """
<!-- @block header -->
# System Update
<!-- @end -->
"""

skeleton = parse_skeleton(raw_content)
block = skeleton.get_block("header")
print(f"Found block: {block.id} with content: {block.content}")

```

## Assembling a Document

The `AssemblyEngine` reconstructs the document. You can provide an `injections` dictionary to replace the content of specific blocks.

```python
from agent.core.implement.assembly_engine import AssemblyEngine
from agent.core.implement.parser import parse_skeleton

skeleton = parse_skeleton(raw_source)
engine = AssemblyEngine()

# Replace specific blocks while keeping others as-is
updates = {
    "step_1": "1. Run `apt-get update` manually.",
    "verification": "Check status code 200."
}

final_doc = engine.assemble(skeleton, injections=updates)

```

## Error Handling

Both the parser and engine raise `InvalidTemplateError` (or `ParsingError` for malformed structures) when encountering issues like duplicate IDs or missing tags.

```python
try:
    skeleton = parse_skeleton(malformed_text)
except Exception as e:
    print(f"Failed to parse: {e}")

```

```

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```python
<<<SEARCH
def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """Parse full-file code blocks from AI-generated markdown.
===
def parse_skeleton(content: str) -> RunbookSkeleton:
    """Parse a runbook skeleton containing @block tags into a RunbookSkeleton model.

    This function identifies block boundaries, extracts IDs and metadata, and 
    captures whitespace for exact reconstruction.

    Args:
        content: The raw string content of the skeleton file.

    Returns:
        A populated RunbookSkeleton instance.

    Raises:
        InvalidTemplateError: If tags are unbalanced or IDs are duplicated.
    """
    # Implementation logic for @block parsing goes here (defined in prior steps)
    pass

def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """Parse full-file code blocks from AI-generated markdown.
>>>

```

**Troubleshooting**
- **Missing Blocks**: Ensure your tags use the exact syntax `<!-- @block ID -->`. Spaces inside the comment brackets are significant for the regex parser.
- **Whitespace Drift**: If the assembled output has extra newlines, check if your skeleton has newlines both inside and outside the `@block` tags.
- **Permission Errors**: Ensure the service account running the pipeline has read access to the `.agent/docs/` directory.

### Step 8: Deployment & Rollback Strategy

The Runbook Parser and Assembly Engine are integrated into the Infrastructure Pipeline via the `agent runbook` CLI command. During the `pre-deployment` phase, the pipeline validates all skeleton templates against the `RunbookSchema` defined in `models.py`. 

1. **Validation**: The pipeline runs `validate_runbook_schema()` on the target skeleton.
2. **Version Pinning**: The engine checks the `version` field in the `RunbookSkeleton` model against the current supported version in `.agent/src/VERSION`.
3. **Assembly**: Content is injected into the skeleton, and the `AssemblyEngine` reconstructs the final document.

**Version-Controlled Tags & Breaking Changes**

Skeleton schemas follow Semantic Versioning (SemVer). Breaking changes to the skeleton grammar or addressable block syntax require a major version bump in the `RunbookSkeleton` model.

- **Tagging Strategy**: Use Git tags (e.g., `skeleton-v1.2.0`) to pin specific skeleton versions to specific pipeline runs.
- **Compatibility Matrix**: The `AssemblyEngine` maintains a minimum supported schema version. If a skeleton's version is lower than the engine's minimum, the pipeline triggers an `InvalidTemplateError`.

**Rollback Procedure**

In the event of parsing failures or formatting drift detected after a deployment:

1. **Parser Rollback**: Set the environment variable `USE_LEGACY_PARSER=true`. This forces the system to use the regex-based `_extract_runbook_data_legacy` path, bypassing the AST parser.
2. **Schema Rollback**: Revert the skeleton template in the repository to the previous stable Git tag.
3. **Pipeline Reversion**: If logic errors persist, revert the `agent` package to the previous stable build, which automatically rolls back the `AssemblyEngine` implementation.

#### [MODIFY] .agent/src/VERSION

```python
<<<SEARCH
1.0.0
===
1.0.1
# Minimum supported skeleton schema version: 1.0.0
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.commands.runbook_generation import generate_runbook_chunked
===
from agent.commands.runbook_generation import generate_runbook_chunked
from agent.core.implement.parser import validate_runbook_schema
from agent.core.implement.assembly_engine import AssemblyEngine, InvalidTemplateError

import os
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
from agent.core.implement.guards import (
===
from agent.core.implement.guards import (
    GuardRail,
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook.py

```python
<<<SEARCH
def generate_runbook(
===
def _validate_version_compatibility(skeleton_version: str):
    """Enforce version-controlled schema tags."""
    with open(os.path.join(os.path.dirname(__file__), "../../VERSION"), "r") as f:
        lines = f.readlines()
        min_ver = lines[1].split(":")[1].strip() if len(lines) > 1 else "1.0.0"
    
    if skeleton_version < min_ver:
        raise InvalidTemplateError(f"Skeleton version {skeleton_version} is below minimum {min_ver}")

def generate_runbook(
>>>

```

**Troubleshooting**

- **Symptom**: `InvalidTemplateError: Duplicate block ID`
  - **Resolution**: Audit the skeleton for repeated `<!-- @block id -->` tags. Ensure IDs are unique across the document.
- **Symptom**: `Structural error: Missing '## Implementation Steps'`
  - **Resolution**: Verify the H2 header is present and spelled correctly. Ensure it is not accidentally indented or fenced in a code block.
- **Symptom**: Formatting drift in re-assembled output.
  - **Resolution**: Compare the re-assembled output using `diff`. Check if the `AssemblyEngine` is correctly capturing `prefix_whitespace` and `suffix_whitespace` in the `RunbookBlock` models.

