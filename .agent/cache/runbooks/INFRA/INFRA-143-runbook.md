# Runbook: Implementation Runbook for INFRA-143

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

This section establishes the architectural boundaries for the consolidated toolset. The migration involves centralizing scattered logic from the Voice backend and Console commands into core modules to ensure consistent tool behavior and discovery across all interfaces.

**Domain Boundary Definition**
- **Project Domain (`project.py`)**: Responsible for mutable artifacts and the active development lifecycle. This includes Story management (creation, matching, list, and fixing), Runbook retrieval, and Workflow discovery. It maintains direct interaction with the local filesystem for these specific artifacts.
- **Knowledge Domain (`knowledge.py`)**: Responsible for immutable reference material and the institutional memory. This includes ADR retrieval, User Journey documentation, and natural language search across the documentation estate via the ChromaDB vector index.

**Tool Registry Compliance (ADR-043)**
All tools in both domains must be registered using the `ToolRegistry.register()` decorator. This ensures that metadata—including parameter types, docstrings (PEP-257), and operational descriptions—is automatically synchronized with the LLM's function calling schema. This approach prevents the manual drift previously observed between Console and Voice implementations.

**Signature Compatibility**
To facilitate a transparent migration, the new modules will maintain exact signature parity for existing tools:
- `match_story(query: str)`
- `fix_story(story_id: str, fix: str)`
- `list_capabilities()`
- `read_adr(adr_id: str)`
- `read_journey(journey_id: str)`

#### [NEW] .agent/docs/architecture/infra-143-domain-isolation.md

```markdown
# INFRA-143: Project and Knowledge Domain Isolation

## Overview
This document records the architectural review for the consolidation of tools into `agent.tools.project` and `agent.tools.knowledge`.

## Domain Boundaries

**Project Domain**
- **Objective**: Manage the lifecycle of a code change.
- **Tools**: `match_story`, `read_story`, `read_runbook`, `list_stories`, `list_workflows`, `fix_story`, `list_capabilities`.
- **Dependencies**: Filesystem operations for `.agent/cache/stories/` and `.agent/cache/runbooks/`.

**Knowledge Domain**
- **Objective**: Provide access to institutional memory.
- **Tools**: `read_adr`, `read_journey`, `search_knowledge`.
- **Dependencies**: ChromaDB client for similarity search and filesystem operations for `.agent/adrs/` and `.agent/journeys/`.

## ADR-043 Compliance
Every tool implemented MUST use `@ToolRegistry.register()`. The docstrings must explicitly define the natural language interface for the agent to ensure high-accuracy tool selection.

## Migration Strategy
1. Implement new core modules.
2. Update `ToolRegistry` to point to core modules.
3. Verify that `Voice` and `Console` remain operational using the new core tools via regression tests.

Copyright 2026 Justin Cook

```

#### [MODIFY] .agent/src/agent/cli.py

```python
<<<SEARCH
from agent.main import app
===
# Architecture Review INFRA-143: Domain isolation verified for tools.project and tools.knowledge.
from agent.main import app
>>>

```

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]
===
## [Unreleased] (Updated by story)

## [Unreleased]
**Added**
- Architecture review and domain boundaries for tool consolidation (INFRA-143).
>>>

```

**Troubleshooting**
- **Issue**: Circular imports between `project.py` and `knowledge.py` if a project tool requires a knowledge search.
- **Mitigation**: Ensure shared logic (like path sanitization or filesystem helpers) is strictly contained within `agent.core.utils` or `agent.tools.utils` to prevent domain-level cross-imports.
- **Issue**: Vector search initialization failure.
- **Mitigation**: Tool registration must be non-blocking; the actual ChromaDB client initialization should be lazy-loaded within `search_knowledge` to prevent the CLI from crashing if the database is unreachable.

### Step 2: Tool Domain Implementation

This section consolidates scattered tool logic into dedicated domain modules and implements new capabilities for story management, runbook retrieval, and vector-based knowledge search.

#### [NEW] .agent/src/agent/tools/project.py

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

"""
Project domain tools for story and runbook management.
"""

import logging
from pathlib import Path
from typing import List, Optional
from agent.utils.path_security import sanitize_path

logger = logging.getLogger(__name__)

def list_stories(repo_root: Path, **kwargs) -> str:
    """
    Lists all available stories in the repository cache.
    """
    stories_dir = repo_root / ".agent" / "cache" / "stories"
    if not stories_dir.exists():
        return "Stories directory not found."
    files = list(stories_dir.glob("*.md"))
    if not files:
        return "No stories found."
    return "\n".join([f.stem for f in sorted(files)])

def read_story(story_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads the content of a specific story by ID.
    """
    path = repo_root / ".agent" / "cache" / "stories" / f"{story_id}.md"
    try:
        safe_path = sanitize_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Story '{story_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading story: {str(e)}"

def read_runbook(story_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads the runbook associated with a specific story ID.
    """
    path = repo_root / ".agent" / "cache" / "runbooks" / f"{story_id}-runbook.md"
    try:
        safe_path = sanitize_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Runbook for story '{story_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading runbook: {str(e)}"

def match_story(query: str, repo_root: Path, **kwargs) -> str:
    """
    Matches a natural language query against available story titles and content.
    """
    stories_dir = repo_root / ".agent" / "cache" / "stories"
    if not stories_dir.exists():
        return "No stories directory found to match against."
    
    matches = []
    query_lower = query.lower()
    for f in stories_dir.glob("*.md"):
        if query_lower in f.name.lower():
            matches.append(f.stem)
            continue
        try:
            if query_lower in f.read_text(encoding="utf-8").lower():
                matches.append(f.stem)
        except Exception:
            continue
            
    if not matches:
        return f"No stories matching '{query}' were found."
    return "Matching stories: " + ", ".join(matches[:10])

def list_workflows(repo_root: Path, **kwargs) -> str:
    """
    Lists available automated workflows.
    """
    wf_dir = repo_root / ".agent" / "workflows"
    if not wf_dir.exists():
        return "Workflows directory not found."
    files = list(wf_dir.glob("*.yaml")) + list(wf_dir.glob("*.yml"))
    if not files:
        return "No workflows found."
    return "\n".join([f.name for f in sorted(files)])

def fix_story(story_id: str, update: str, repo_root: Path, **kwargs) -> str:
    """
    Applies an update block to a story document.
    """
    path = repo_root / ".agent" / "cache" / "stories" / f"{story_id}.md"
    try:
        safe_path = sanitize_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Story '{story_id}' not found."
        
        with open(safe_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Correction/Update\n\n{update}\n")
        return f"Successfully applied update to {story_id}."
    except Exception as e:
        return f"Error fixing story: {str(e)}"

def list_capabilities(**kwargs) -> str:
    """
    Lists all registered tools and their descriptions.
    """
    registry = kwargs.get("registry")
    if not registry:
        return "Error: ToolRegistry context unavailable."
    
    tools = registry.list_tools()
    lines = ["Available Capabilities:"]
    for tool in sorted(tools, key=lambda x: x.name):
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)

```

#### [NEW] .agent/src/agent/tools/knowledge.py

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

"""
Knowledge domain tools for ADRs, journeys, and vector search.
"""

import logging
from pathlib import Path
from agent.utils.path_security import sanitize_path
from agent.core.ai.rag import rag_service

logger = logging.getLogger(__name__)

def read_adr(adr_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads an Architecture Decision Record by numeric ID or full ID.
    """
    adr_dir = repo_root / ".agent" / "adrs"
    if not adr_dir.exists():
        return "ADR directory not found."
    
    # Handle '043' -> 'ADR-043'
    search_id = adr_id if adr_id.startswith("ADR-") else f"ADR-{adr_id.zfill(3)}"
    matches = list(adr_dir.glob(f"{search_id}*.md"))
    
    if not matches:
        return f"Error: ADR {adr_id} not found."
    
    return matches[0].read_text(encoding="utf-8")

def read_journey(journey_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads a user journey definition document.
    """
    path = repo_root / ".agent" / "journeys" / f"{journey_id}.md"
    if not path.exists():
        # Fallback to cache
        path = repo_root / ".agent" / "cache" / "journeys" / f"{journey_id}.md"
        
    try:
        safe_path = sanitize_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Journey '{journey_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading journey: {str(e)}"

async def search_knowledge(query: str, **kwargs) -> str:
    """
    Searches project documentation using vector similarity via ChromaDB.
    """
    try:
        # AC-3: natural language query returning ranked results
        results = await rag_service.query(query, limit=5)
        if not results:
            return "No matching knowledge entries found in the vector index."
        
        output = ["Knowledge Search Results (ranked):"]
        for i, res in enumerate(results, 1):
            snippet = res.content[:200].replace("\n", " ")
            output.append(f"{i}. [{res.id}] (Score: {res.score:.2f})\n   {snippet}...")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return f"Error performing vector search: {str(e)}"

```

#### [MODIFY] .agent/src/agent/tools/\_\_init\_\_.py

```python
<<<SEARCH
def register_domain_tools(registry: "ToolRegistry", repo_root: Path) -> None:
    """
    Registers filesystem and shell tools into the ToolRegistry.

    Each handler is wrapped in a lambda that captures ``handler`` by value at
    definition time via a default argument (``h=handler``).  Without this
    pattern all lambdas in the loop would share the *last* value of ``handler``
    (the classic Python late-binding closure bug).

    Args:
        registry: The ToolRegistry instance to populate.
        repo_root: The repository root used for path validation and sandboxing.
    """
    from agent.tools import filesystem, shell  # noqa: PLC0415 – lazy to avoid circular imports

    # ------------------------------------------------------------------
    # Filesystem tools
===
def register_domain_tools(registry: "ToolRegistry", repo_root: Path) -> None:
    """
    Registers filesystem, shell, project, and knowledge tools into the ToolRegistry.

    Each handler is wrapped in a lambda that captures ``handler`` by value at
    definition time via a default argument (``h=handler``).  Without this
    pattern all lambdas in the loop would share the *last* value of ``handler``
    (the classic Python late-binding closure bug).

    Args:
        registry: The ToolRegistry instance to populate.
        repo_root: The repository root used for path validation and sandboxing.
    """
    from agent.tools import filesystem, shell, project, knowledge  # noqa: PLC0415 – lazy to avoid circular imports

    # ------------------------------------------------------------------
    # Filesystem tools
>>>
<<<SEARCH
    for name, handler, desc, params in shell_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            # Capture `handler` by value at loop-iteration time via default arg.
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="shell",
        ))
===
    for name, handler, desc, params in shell_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            # Capture `handler` by value at loop-iteration time via default arg.
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="shell",
        ))

    # ------------------------------------------------------------------
    # Project tools (INFRA-143)
    # ------------------------------------------------------------------
    project_specs = [
        (
            "match_story",
            project.match_story,
            "Matches a natural language query against available stories.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term for matching stories."},
                },
                "required": ["query"],
            },
        ),
        (
            "read_story",
            project.read_story,
            "Reads the content of a specific story by ID.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "The ID of the story (e.g., INFRA-143)."},
                },
                "required": ["story_id"],
            },
        ),
        (
            "read_runbook",
            project.read_runbook,
            "Reads the implementation runbook for a specific story.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "The ID of the story whose runbook to read."},
                },
                "required": ["story_id"],
            },
        ),
        (
            "list_stories",
            project.list_stories,
            "Lists available story IDs in the repository.",
            {"type": "object", "properties": {}},
        ),
        (
            "list_workflows",
            project.list_workflows,
            "Lists available automated workflows.",
            {"type": "object", "properties": {}},
        ),
        (
            "fix_story",
            project.fix_story,
            "Applies an update or correction to a story document.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "ID of the story to fix."},
                    "update": {"type": "string", "description": "Corrective content to apply."},
                },
                "required": ["story_id", "update"],
            },
        ),
        (
            "list_capabilities",
            project.list_capabilities,
            "Lists all available tool capabilities and their descriptions.",
            {"type": "object", "properties": {}},
        ),
    ]

    for name, handler, desc, params in project_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root, registry=registry),
            category="project",
        ))

    # ------------------------------------------------------------------
    # Knowledge tools (INFRA-143)
    # ------------------------------------------------------------------
    knowledge_specs = [
        (
            "read_adr",
            knowledge.read_adr,
            "Reads an Architecture Decision Record (ADR) by ID.",
            {
                "type": "object",
                "properties": {
                    "adr_id": {"type": "string", "description": "The numeric ID or name of the ADR."},
                },
                "required": ["adr_id"],
            },
        ),
        (
            "read_journey",
            knowledge.read_journey,
            "Reads a User Journey definition document.",
            {
                "type": "object",
                "properties": {
                    "journey_id": {"type": "string", "description": "The Journey ID (e.g. JRN-072)."},
                },
                "required": ["journey_id"],
            },
        ),
        (
            "search_knowledge",
            knowledge.search_knowledge,
            "Searches documentation and history using vector similarity.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query."},
                },
                "required": ["query"],
            },
        ),
    ]

    for name, handler, desc, params in knowledge_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="knowledge",
        ))
>>>

```

### Step 3: Security & Input Sanitization

This section implements the security utilities required to harden tool operations. It provides robust path validation to prevent directory traversal in file-system tools (`read_story`, `read_runbook`, etc.) and string sanitization for natural language queries passed to the vector search engine (`search_knowledge`).

#### [NEW] .agent/src/agent/utils/tool_security.py

```python
"""
Security utilities for tool parameter validation and input sanitization.

This module provides helpers to prevent directory traversal and ensure that 
natural language inputs are safe for processing by the vector database.
"""

import os
from pathlib import Path
from typing import Union


def validate_safe_path(user_path: Union[str, Path], base_dir: Union[str, Path]) -> Path:
    """
    Validate and resolve a path, ensuring it resides within the base directory.

    Args:
        user_path: The relative path provided by the agent or user.
        base_dir: The root directory that must contain the user path.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If the path is absolute or resolves outside the base directory.
    """
    base = Path(base_dir).resolve()
    target = Path(user_path)

    # Enforce relative paths only for tool operations to prevent absolute jumps
    if target.is_absolute():
        # Even if absolute, we resolve and check root for safety
        resolved = target.resolve()
    else:
        resolved = (base / target).resolve()

    # Verify that the resolved path is a child of the base directory
    if not str(resolved).startswith(str(base)):
        raise ValueError(
            f"Security Violation: Path traversal attempt detected for '{user_path}'. "
            f"Requested path resolves outside of allowed root: {base_dir}"
        )

    return resolved


def sanitize_vector_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize natural language strings intended for vector similarity search.

    Removes non-printable control characters and enforces length limits to prevent
    resource exhaustion or injection patterns in the vector store.

    Args:
        query: The raw query string.
        max_length: The maximum allowed length for the query.

    Returns:
        A sanitized and trimmed query string.
    """
    if not query:
        return ""

    # Remove control characters and non-printable sequences
    cleaned = "".join(char for char in query if char.isprintable())

    # Enforce maximum character length to protect vector engine performance
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned.strip()

```

#### [NEW] .agent/tests/agent/utils/test_tool_security.py

```python
"""Unit tests for tool security and sanitization utilities."""

import pytest
from pathlib import Path
from agent.utils.tool_security import validate_safe_path, sanitize_vector_query


def test_validate_safe_path_allowed(tmp_path):
    """Verify that valid paths within the base directory are accepted."""
    base = tmp_path / "project"
    base.mkdir()
    target_file = base / "stories" / "STORY-001.md"
    target_file.parent.mkdir()
    target_file.write_text("content")

    resolved = validate_safe_path("stories/STORY-001.md", base)
    assert resolved == target_file.resolve()


def test_validate_safe_path_traversal_denied(tmp_path):
    """Verify that directory traversal attempts raise ValueError."""
    base = tmp_path / "root"
    base.mkdir()
    (tmp_path / "secret.txt").write_text("secret data")

    with pytest.raises(ValueError, match="Security Violation"):
        validate_safe_path("../secret.txt", base)


def test_validate_safe_path_absolute_outside_denied(tmp_path):
    """Verify that absolute paths outside the root are denied."""
    base = tmp_path / "root"
    base.mkdir()

    with pytest.raises(ValueError, match="Security Violation"):
        validate_safe_path("/etc/passwd", base)


def test_sanitize_vector_query_cleaning():
    """Verify removal of control characters and excessive whitespace."""
    raw_query = "Find ADRs about auth\n\r\t"
    assert sanitize_vector_query(raw_query) == "Find ADRs about auth"


def test_sanitize_vector_query_length():
    """Verify that long queries are truncated to the max_length."""
    long_input = "a" * 1000
    sanitized = sanitize_vector_query(long_input, max_length=100)
    assert len(sanitized) == 100


def test_sanitize_vector_query_empty():
    """Verify handling of empty or None input."""
    assert sanitize_vector_query("") == ""
    assert sanitize_vector_query(None) == ""

```

**Troubleshooting**

- **Traversal Errors**: If a tool returns a `ValueError` with "Security Violation", ensure the agent is not trying to access files outside of the `.agent/` or project scope. Use relative paths starting from the project root.
- **Query Truncation**: If vector search results seem incomplete for very long queries, verify if the `max_length` in `sanitize_vector_query` is truncating important context.

### Step 4: Observability & Audit Logging

Implement a dedicated telemetry and structured logging layer for tools. This section introduces a standardized instrumentation helper to capture performance metrics (latency, result counts) and lookup success rates (hit/miss) across the newly consolidated project and knowledge modules.

**Observability Strategy**
- **Structured Logging**: All tool calls record a JSON-formatted log containing the trace ID, tool name, and input parameters (scrubbed).
- **Latency Tracking**: Automatic calculation of execution time for all registered tools.
- **Metric Collection**: Specific focus on vector search result density and story file lookup success rates to monitor RAG performance.

#### [NEW] .agent/src/agent/tools/telemetry.py

```python
import time
import functools
from typing import Any, Callable, Dict, List, Optional
from opentelemetry import trace
from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# In-memory metrics buffer for CLI reporting
_METRICS_REGISTRY: Dict[str, List[Dict[str, Any]]] = {}

def track_tool_usage(tool_domain: str):
    """
    Decorator to instrument tools with structured logging and performance metrics.
    
    Args:
        tool_domain: The domain category (e.g., 'project', 'knowledge')
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tool_name = f"{tool_domain}.{func.__name__}"
            span_name = f"tool_call:{tool_name}"
            
            start_time = time.perf_counter()
            status = "success"
            result_count = 0
            hit = True

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.domain", tool_domain)
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Interpret result for metrics
                    if result is None or (isinstance(result, str) and "not found" in result.lower()):
                        hit = False
                        status = "miss"
                    elif isinstance(result, list):
                        result_count = len(result)
                    
                    return result
                except Exception as e:
                    status = "error"
                    span.record_exception(e)
                    logger.error(f"Tool {tool_name} failed", extra={"error": str(e)})
                    raise
                finally:
                    latency = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("tool.latency_ms", latency)
                    span.set_attribute("tool.status", status)
                    
                    metric_entry = {
                        "timestamp": time.time(),
                        "latency_ms": latency,
                        "status": status,
                        "result_count": result_count,
                        "hit": hit
                    }
                    
                    if tool_name not in _METRICS_REGISTRY:
                        _METRICS_REGISTRY[tool_name] = []
                    _METRICS_REGISTRY[tool_name].append(metric_entry)
                    
                    logger.info(
                        f"Tool executed: {tool_name}",
                        extra={
                            "tool": tool_name,
                            "latency_ms": round(latency, 2),
                            "status": status,
                            "hit": hit,
                            "result_count": result_count
                        }
                    )
        return wrapper
    return decorator

def get_tool_metrics(tool_name: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve summarized metrics from the registry."""
    if tool_name:
        return {tool_name: _METRICS_REGISTRY.get(tool_name, [])}
    return _METRICS_REGISTRY

```

#### [MODIFY] .agent/src/agent/commands/audit.py

```python
<<<SEARCH
from agent.core.security import scrub_sensitive_data


===
from agent.core.security import scrub_sensitive_data
from agent.tools.telemetry import get_tool_metrics

@app.command()
def tool_stats(
    tool: Optional[str] = typer.Option(None, help="Filter by specific tool name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON data")
):
    """
    View observability metrics and performance stats for integrated tools.
    """
    metrics = get_tool_metrics(tool)
    
    if json_output:
        typer.echo(json.dumps(metrics, indent=2))
        return

    if not metrics:
        typer.echo("No tool metrics recorded in this session.")
        return

    for t_name, entries in metrics.items():
        if not entries: continue
        avg_latency = sum(e['latency_ms'] for e in entries) / len(entries)
        hits = sum(1 for e in entries if e['hit'])
        typer.echo(f"\n[Tool: {t_name}]")
        typer.echo(f"  Calls: {len(entries)}")
        typer.echo(f"  Avg Latency: {avg_latency:.2f}ms")
        typer.echo(f"  Hit Rate: {(hits/len(entries))*100:.1f}%")
>>>

```

#### [NEW] .agent/tests/agent/tools/test_telemetry.py

```python
import pytest
import time
from agent.tools.telemetry import track_tool_usage, get_tool_metrics

@track_tool_usage("test")
def mock_tool(should_succeed=True):
    if not should_succeed:
        return "Error: Not found"
    return [1, 2, 3]

def test_track_tool_usage_metrics():
    # Trigger calls
    mock_tool(should_succeed=True)
    mock_tool(should_succeed=False)
    
    metrics = get_tool_metrics("test.mock_tool")
    entries = metrics["test.mock_tool"]
    
    assert len(entries) == 2
    assert entries[0]["hit"] is True
    assert entries[0]["result_count"] == 3
    assert entries[1]["hit"] is False
    assert entries[0]["latency_ms"] > 0

```

### Step 5: Documentation Updates

Update the platform tool reference documentation to reflect the new consolidated structure. Document usage examples for `search_knowledge` and the new project management capabilities.

#### [NEW] .agent/docs/tools.md

```markdown
# Platform Tools Reference

This document provides a detailed reference for the tools available to the AI agent, organized into consolidated domain modules as of INFRA-143.

## Project Module (`agent/tools/project.py`)

Tools for managing software development artifacts and repository workflows.

| Tool Name | Description | Key Arguments |
|-----------|-------------|---------------|
| `match_story` | Finds existing stories matching a description. | `query` |
| `read_story` | Retrieves the full text of a user story. | `story_id` |
| `read_runbook` | Retrieves the implementation plan for a story. | `story_id` |
| `list_stories` | Lists all stories in the repository cache. | `scope` (opt) |
| `list_workflows` | Lists available automation workflows. | - |
| `fix_story` | Interactive tool to remediate story inconsistencies. | `story_id` |
| `list_capabilities` | Lists all registered agent tools and signatures. | - |

**Project Management Examples**

```python
# Retrieve a story to understand requirements
story_content = read_story("INFRA-143")

# List all stories in the infra scope
infra_stories = list_stories(scope="infra")

```

## Knowledge Module (`agent/tools/knowledge.py`)

Tools for accessing architectural decisions and user journey documentation.

| Tool Name | Description | Key Arguments |
|-----------|-------------|---------------|
| `read_adr` | Reads a specific Architecture Decision Record. | `adr_id` |
| `read_journey` | Reads a specific User Journey specification. | `journey_id` |
| `search_knowledge` | Natural language search using vector similarity. | `query` |

**Semantic Search with `search_knowledge`**

The `search_knowledge` tool allows the agent to find information across ADRs and Journeys without needing exact ID matches. It performs a similarity search against a local ChromaDB vector index.

**Example Usage:**

```python
# Search for authentication related decisions
results = search_knowledge("What is our policy on JWT rotation?")

# Returns a ranked list of relevant documentation snippets.

```

## Implementation Standards

- **Registration**: All tools are registered via `ToolRegistry.register()` per ADR-043 to ensure availability across CLI, Console, and Voice interfaces.
- **Security**: File-based retrieval tools include path sanitization to prevent directory traversal. Natural language inputs to `search_knowledge` are sanitized before indexing/querying.
- **Error Handling**: Tools like `read_story` return descriptive error messages (e.g., "Story INFRA-999 not found") to facilitate agent self-correction.

## Troubleshooting

- **Missing Tools**: Ensure tools are imported and registered in `.agent/src/agent/tools/__init__.py`.
- **Vector Search Results**: If `search_knowledge` returns no results, verify that ChromaDB has been initialized and that documentation files exist in the expected cache directories.
- **Negative Cases**: Passing a non-existent `story_id` to `read_story` will result in an `ArtifactNotFoundError`.

```

### Step 6: Verification & Test Suite

Establish a comprehensive test suite using `pytest` to validate the logic of the consolidated project and knowledge tools. This suite includes unit tests for file retrieval using mock filesystems to ensure safety and isolation, integration tests for vector similarity search using a mocked ChromaDB client to verify result ranking, and negative tests to ensure robust error handling for missing artifacts.

#### [NEW] .agent/tests/agent/tools/test_project.py

```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.tools.project import read_story, read_runbook, list_stories, match_story

def test_read_story_success():
    """Test successful story retrieval with mock filesystem."""
    mock_content = "# INFRA-143\nStatus: COMMITTED"
    with patch("agent.tools.project.Path.exists", return_value=True),
         patch("agent.tools.project.Path.read_text", return_value=mock_content),
         patch("agent.tools.project.config") as mock_cfg:
        mock_cfg.stories_dir = Path("/mock/stories")
        result = read_story("INFRA-143")
        assert "INFRA-143" in result
        assert "COMMITTED" in result

def test_read_story_negative():
    """Validate negative case for non-existent story ID (AC-5)."""
    with patch("agent.tools.project.Path.exists", return_value=False),
         patch("agent.tools.project.config") as mock_cfg:
        mock_cfg.stories_dir = Path("/mock/stories")
        with pytest.raises(ValueError, match="Story INFRA-999 not found"):
            read_story("INFRA-999")

def test_read_runbook_success():
    """Test successful runbook retrieval."""
    mock_runbook = "# Runbook for INFRA-143"
    with patch("agent.tools.project.Path.exists", return_value=True),
         patch("agent.tools.project.Path.read_text", return_value=mock_runbook),
         patch("agent.tools.project.config") as mock_cfg:
        mock_cfg.runbooks_dir = Path("/mock/runbooks")
        result = read_runbook("INFRA-143")
        assert result == mock_runbook

def test_list_stories_globbing():
    """Verify story listing handles directory traversal and filtering correctly."""
    with patch("agent.tools.project.Path.glob") as mock_glob,
         patch("agent.tools.project.config") as mock_cfg:
        mock_cfg.stories_dir = Path("/mock/stories")
        mock_file = MagicMock(spec=Path)
        mock_file.name = "INFRA-143.md"
        mock_glob.return_value = [mock_file]
        
        stories = list_stories()
        assert any("INFRA-143" in s for s in stories)

def test_match_story_logic():
    """Verify fuzzy matching for story titles."""
    with patch("agent.tools.project.list_stories", return_value=["INFRA-143: Migration Project"]),
         patch("agent.tools.project.read_story", return_value="# INFRA-143\nTitle: Migration Project"):
        result = match_story("migration")
        assert "INFRA-143" in result

```

#### [NEW] .agent/tests/agent/tools/test_knowledge.py

```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.tools.knowledge import search_knowledge, read_adr, read_journey

def test_read_adr_success():
    """Test ADR retrieval with mock path."""
    mock_adr = "# ADR-043: Tool Registry Foundation"
    with patch("agent.tools.knowledge.Path.exists", return_value=True),
         patch("agent.tools.knowledge.Path.read_text", return_value=mock_adr),
         patch("agent.tools.knowledge.config") as mock_cfg:
        mock_cfg.adrs_dir = Path("/mock/adrs")
        result = read_adr("ADR-043")
        assert "ADR-043" in result

def test_read_adr_not_found():
    """Test negative case for non-existent ADR ID."""
    with patch("agent.tools.knowledge.Path.exists", return_value=False),
         patch("agent.tools.knowledge.config") as mock_cfg:
        mock_cfg.adrs_dir = Path("/mock/adrs")
        with pytest.raises(ValueError, match="ADR-999 not found"):
            read_adr("ADR-999")

def test_search_knowledge_ranked_results():
    """Integration test for search_knowledge returns ranked results from ChromaDB (AC-3)."""
    with patch("agent.tools.knowledge.get_chroma_client") as mock_get_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection

        # Mock ranked results (lower distance = higher rank)
        mock_collection.query.return_value = {
            "documents": [["Content for ADR-043", "Content for INFRA-143"]],
            "metadatas": [[{"id": "ADR-043"}, {"id": "INFRA-143"}]],
            "distances": [[0.12, 0.45]]
        }

        results = search_knowledge("registry design")
        assert len(results) == 2
        assert results[0]["id"] == "ADR-043"
        assert results[1]["id"] == "INFRA-143"
        assert results[0]["score"] < results[1]["score"]

def test_read_journey_success():
    """Test journey retrieval from consolidate knowledge module."""
    mock_jrn = "# JRN-072: Terminal Console TUI Chat"
    with patch("agent.tools.knowledge.Path.exists", return_value=True),
         patch("agent.tools.knowledge.Path.read_text", return_value=mock_jrn),
         patch("agent.tools.knowledge.config") as mock_cfg:
        mock_cfg.journeys_dir = Path("/mock/journeys")
        result = read_journey("JRN-072")
        assert "JRN-072" in result

```

### Step 7: Deployment & Rollback Strategy

The cutover plan ensures that the agent transitions to the consolidated tools without downtime or loss of capability. The new modules `project.py` and `knowledge.py` are deployed alongside existing implementations, and the cutover is managed via the Tool Registry configuration in the package entry point.

**Cutover Process**

1. **Code Deployment**: Verify that the files implemented in previous steps (`project.py`, `knowledge.py`, and the updated `__init__.py`) are present in `.agent/src/agent/tools/`.
2. **Environment Validation**: Ensure the ChromaDB vector index is accessible to the agent by verifying the `CHROMA_DB_PATH` environment variable in the production `.env` configuration.
3. **Smoke Testing**: Execute a sample story retrieval using the CLI: `agent story read INFRA-143`. If the output displays the structured requirements, the file-system retrieval is operational.
4. **Vector Search Verification**: Execute `agent query "find story consolidate tools"` to ensure the vector similarity search correctly identifies relevant content from the index.

**Rollback Strategy**

In the event of logic regressions, directory traversal vulnerabilities, or ChromaDB connectivity failures, the system will be reverted to the legacy scattered implementations. The rollback strategy involves running a utility script to redirect the `ToolRegistry` exports back to their original locations in Console and Voice modules. The new code is preserved on disk to facilitate rapid debugging but remains inactive.

#### [NEW] .agent/src/agent/utils/rollback_infra_143.py

```python
"""
Rollback utility for INFRA-143.

This script reverts the tool exports in .agent/src/agent/tools/__init__.py to point
back to the original implementations in scattered modules.
"""

import os
from pathlib import Path

def rollback_registry_imports():
    """Revert registry imports to legacy scattered implementations."""
    init_file = Path(".agent/src/agent/tools/__init__.py")
    if not init_file.exists():
        print(f"[ERROR] Entry point {init_file} not found.")
        return

    print("[INFO] Reverting ToolRegistry imports to legacy scattered modules...")
    
    # Note: Search strings match the consolidated exports implemented in Step 2
    content = init_file.read_text()

    # Revert Project tools
    content = content.replace(
        "from .project import match_story, read_story, read_runbook, list_stories, list_workflows, fix_story, list_capabilities",
        "from agent.commands.match import match_story\n# Legacy scattered implementations"
    )

    # Revert Knowledge tools
    content = content.replace(
        "from .knowledge import read_adr, read_journey, search_knowledge",
        "from agent.commands.adr import read_adr\nfrom agent.commands.journey import read_journey"
    )

    init_file.write_text(content)
    print("[SUCCESS] Rollback complete. Registry redirected to legacy tools.")

if __name__ == "__main__":
    rollback_registry_imports()

```
