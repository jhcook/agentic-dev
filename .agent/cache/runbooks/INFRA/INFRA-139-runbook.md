# STORY-ID: INFRA-139: Core Tool Registry and Foundation

## State

ACCEPTED

## Goal Description

This story establishes the centralized `ToolRegistry` and foundational `Tool` / `ToolResult` data models within the `.agent/src/agent/tools/` package. By unifying how tools are defined, registered, and discovered, this foundation enables consistent tool execution across both Console (TUI) and Voice interfaces. It includes a security-mandated audit trail for unrestricting sensitive tools and ensures O(1) discovery performance through a dictionary-backed registry. Per architectural governance, this design is formalized in a new Architecture Decision Record (ADR) to document the rationale for the shared package and O(1) lookup strategy.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Panel Review Findings

### @Architect
- Validated. The `ToolRegistry` implements a dictionary-backed store for O(1) lookup.
- The package location `.agent/src/agent/tools/` is appropriate for a shared utility that will be used by both CLI commands and service layers.
- No circular dependencies are introduced as the registry depends only on `pydantic` and `agent.core.governance`.
- **Advice Applied**: Create and ratify a new Architecture Decision Record (ADR) to document the design, models, and shared package structure.

### @Qa
- Comprehensive unit tests are required to verify tool registration, duplicate name rejection, and category filtering.
- A specific test case for the audit logging during tool unrestriction must be included.
- **Advice Applied**: Added a unit test to verify the error path when `unrestrict_tool` is called for a non-existent tool.

### @Security
- `unrestrict_tool()` correctly integrates with `log_governance_event` to ensure all privilege escalations (making a restricted tool available) are recorded.
- Pydantic models enforce strict schema validation for tool parameters, reducing the risk of malformed inputs being passed to handlers.

### @Product
- Acceptance criteria (AC-1 through AC-3) are fully met by the implementation.
- The standard `Tool` interface provides the necessary metadata (name, description, schema) for LLMs to effectively use these tools.

### @Observability
- The unrestriction of tools is identified as a high-value event for the audit log.
- Errors in the registry (e.g., lookup failures or registration conflicts) use a specific `ToolRegistryError` for better error tracking.

### @Docs
- Full PEP-257 docstrings are provided for the module, classes, and methods.
- The new `agent/tools` package is clean and ready for integration in subsequent tool-building stories.
- **Advice Applied**: Update `CHANGELOG.md` with the INFRA-139 entry and ensure the Architecture Decision Record (ADR) is ratified and merged.

### @Compliance
- Apache 2.0 License headers are present in all new files.
- No PII or sensitive secrets are stored within the tool registry itself.

### @Backend
- Strict typing is enforced across all methods.
- Pydantic v2 patterns are used for the models.
- **Advice Applied**: Updated the test suite to use the correct `MockerFixture` type hint for `pytest-mock`.

## Codebase Introspection

### Targeted File Contents (from source)

(Note: The targeted context for `.agent/src/agent/tools/__init__.py` exists in the input but the folder is missing from the tree. I will use `[NEW]` to establish the foundation as the previous validation failed on the path.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/src/agent/tools/tests/test_registry.py` | N/A | `.agent/src/agent/tools/__init__.py` | Create new unit tests for the registry, including error paths and audit logs. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Duplicate Registration Error | AC-Negative | Raises ToolRegistryError | Yes |
| Audit Logging | NFR-Security | Calls log_governance_event on unrestriction | Yes |
| Lookup Complexity | NFR-Performance | O(1) | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Establish the `agent/tools` namespace for future tool consolidation (moving tools out of `voice/tools/`).

## Implementation Steps

### Step 1: Create Tool Registry Foundation

#### [NEW] .agent/src/agent/tools/\_\_init\_\_.py

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
Core tool registry and foundational models for agentic tools.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from agent.core.governance import log_governance_event


class ToolRegistryError(Exception):
    """
    Raised when a tool registry operation fails.
    """
    pass


class ToolResult(BaseModel):
    """
    Standard container for the result of a tool execution.
    """
    success: bool = Field(..., description="Whether the tool execution succeeded")
    output: Optional[Any] = Field(None, description="The output data from the tool")
    error: Optional[str] = Field(None, description="The error message if the tool failed")


class Tool(BaseModel):
    """
    Definition of a tool that can be registered and executed by an agent.
    """
    name: str = Field(..., description="Unique name of the tool")
    description: str = Field(..., description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(..., description="JSON schema of the tool parameters")
    handler: Callable[..., Any] = Field(..., description="The function to execute")
    category: str = Field("general", description="The domain category of the tool (e.g., filesystem, shell)")
    restricted: bool = Field(True, description="Whether the tool requires explicit authorization to run")


class ToolRegistry:
    """
    Central registry for managing agent tools.
    """

    def __init__(self) -> None:
        """
        Initialize the registry with an empty tool map.
        """
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Registers a new tool in the registry.

        Args:
            tool: The Tool instance to register.

        Raises:
            ToolRegistryError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ToolRegistryError(f"Tool with name '{tool.name}' already registered.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        """
        Retrieves a tool by its name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The requested Tool instance.

        Raises:
            ToolRegistryError: If the tool is not found.
        """
        if name not in self._tools:
            raise ToolRegistryError(f"Tool '{name}' not found.")
        return self._tools[name]

    def list_tools(self, category: Optional[str] = None) -> List[Tool]:
        """
        Lists tools, optionally filtered by category.

        Args:
            category: Optional category name to filter by.

        Returns:
            A list of registered Tool instances.
        """
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def unrestrict_tool(self, name: str) -> None:
        """
        Removes the restriction flag from a tool and logs the audit event.

        Args:
            name: The name of the tool to unrestrict.

        Raises:
            ToolRegistryError: If the tool is not found.
        """
        if name not in self._tools:
            raise ToolRegistryError(f"Tool '{name}' not found.")

        self._tools[name].restricted = False
        log_governance_event(
            "tool_unrestrict",
            f"Tool '{name}' has been unrestricted for general use."
        )
```

### Step 2: Create Test Package Initialization

#### [NEW] .agent/src/agent/tools/tests/\_\_init\_\_.py

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
Tests for the agent tools package.
"""
```

### Step 3: Implement Registry Unit Tests

#### [NEW] .agent/src/agent/tools/tests/test_registry.py

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
Unit tests for the ToolRegistry and Tool models.
"""

import pytest
from pytest_mock import MockerFixture
from agent.tools import ToolRegistry, Tool, ToolRegistryError


def test_tool_registry_registration() -> None:
    """
    Verify that a tool can be registered and retrieved.
    """
    registry = ToolRegistry()
    def mock_handler() -> str:
        """Return a fixed string for testing."""
        return "ok"

    tool = Tool(
        name="test_tool",
        description="A test tool",
        parameters={},
        handler=mock_handler
    )
    registry.register(tool)
    assert registry.get_tool("test_tool") == tool


def test_tool_registry_duplicate_rejection() -> None:
    """
    Verify that registering a duplicate tool name raises ToolRegistryError.
    """
    registry = ToolRegistry()
    def mock_handler() -> str:
        """Return a fixed string for testing."""
        return "ok"

    tool = Tool(name="dup", description="d1", parameters={}, handler=mock_handler)
    registry.register(tool)

    with pytest.raises(ToolRegistryError, match="already registered"):
        registry.register(tool)


def test_tool_registry_filtering() -> None:
    """
    Verify that tools can be filtered by category.
    """
    registry = ToolRegistry()
    def h() -> None:
        """No-op handler for testing."""
        pass

    registry.register(Tool(name="t1", description="d", parameters={}, handler=h, category="fs"))
    registry.register(Tool(name="t2", description="d", parameters={}, handler=h, category="shell"))

    assert len(registry.list_tools()) == 2
    assert len(registry.list_tools(category="fs")) == 1
    assert registry.list_tools(category="fs")[0].name == "t1"


def test_tool_unrestriction_logs_audit(mocker: MockerFixture) -> None:
    """
    Verify that unrestricting a tool updates the flag and logs a governance event.
    """
    mock_log = mocker.patch("agent.tools.log_governance_event")
    registry = ToolRegistry()
    def h() -> None:
        """No-op handler for testing."""
        pass
    
    registry.register(Tool(name="secret", description="d", parameters={}, handler=h, restricted=True))
    registry.unrestrict_tool("secret")
    
    assert registry.get_tool("secret").restricted is False
    mock_log.assert_called_once_with(
        "tool_unrestrict",
        "Tool 'secret' has been unrestricted for general use."
    )


def test_unrestrict_tool_not_found() -> None:
    """
    Verify that unrestricting a non-existent tool raises ToolRegistryError.
    """
    registry = ToolRegistry()
    with pytest.raises(ToolRegistryError, match="not found"):
        registry.unrestrict_tool("non_existent_tool")


def test_get_tool_not_found() -> None:
    """
    Verify that getting a non-existent tool raises ToolRegistryError.
    """
    registry = ToolRegistry()
    with pytest.raises(ToolRegistryError, match="not found"):
        registry.get_tool("missing")
```

## Verification Plan

### Automated Tests

- [ ] Run the new registry tests:

  ```bash
  pytest .agent/src/agent/tools/tests/test_registry.py
  ```

- [ ] Verify full repository test suite passes (ensure no regressions):

  ```bash
  pytest .agent/src/agent/
  ```

### Manual Verification

- [ ] Verify the file structure in the file tree:

  ```bash
  ls -R .agent/src/agent/tools/
  ```

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-139
- [ ] PEP-257 docstrings present for all new classes and methods.
- [ ] ADR for Tool Registry foundation ratified and merged.

### Observability

- [ ] Logs are structured and free of PII
- [ ] `log_governance_event` is correctly called for sensitive operations.

### Testing

- [ ] All existing tests pass
- [ ] New tests added for each new public interface, including error scenarios.

## Copyright

Copyright 2026 Justin Cook
