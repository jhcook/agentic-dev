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
