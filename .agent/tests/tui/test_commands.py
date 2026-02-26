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

"""Tests for console command parser (INFRA-087)."""

import tempfile
from pathlib import Path

import pytest
import yaml

from agent.tui.commands import (
    InputType,
    discover_roles,
    discover_workflows,
    format_help_text,
    parse_input,
)


@pytest.fixture
def workflows_dir(tmp_path):
    """Create a temp workflows directory with sample files."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()

    # Create sample workflow files with frontmatter
    (wf_dir / "commit.md").write_text(
        "---\ndescription: Commit changes using conventional commits\n---\n# Commit\nSteps..."
    )
    (wf_dir / "preflight.md").write_text(
        "---\ndescription: Run preflight governance checks\n---\n# Preflight\nSteps..."
    )
    (wf_dir / "pr.md").write_text(
        "---\ndescription: Create a pull request\n---\n# PR\nSteps..."
    )
    return wf_dir


@pytest.fixture
def agents_yaml(tmp_path):
    """Create a temp agents.yaml with sample roles."""
    path = tmp_path / "agents.yaml"
    data = {
        "team": [
            {
                "role": "architect",
                "name": "System Architect",
                "description": "Guardian of system design.",
                "responsibilities": ["Review ADRs"],
                "governance_checks": ["Do ADRs exist?"],
            },
            {
                "role": "security",
                "name": "Security (CISO)",
                "description": "Enforcer of security controls.",
                "responsibilities": ["Scan for secrets"],
                "governance_checks": ["No PII in logs"],
            },
        ]
    }
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


class TestDiscovery:
    def test_discover_workflows(self, workflows_dir):
        wfs = discover_workflows(workflows_dir)
        assert "commit" in wfs
        assert "preflight" in wfs
        assert wfs["commit"] == "Commit changes using conventional commits"

    def test_discover_workflows_empty(self, tmp_path):
        assert discover_workflows(tmp_path / "nonexistent") == {}

    def test_discover_roles(self, agents_yaml):
        roles = discover_roles(agents_yaml)
        assert "architect" in roles
        assert "security" in roles
        assert "Guardian" in roles["architect"]

    def test_discover_roles_missing(self, tmp_path):
        assert discover_roles(tmp_path / "no.yaml") == {}


class TestParseInput:
    """Tests for the command parser."""

    def _workflows(self):
        return {"commit": "Commit", "preflight": "Preflight", "pr": "PR"}

    def _roles(self):
        return {"architect": "System Architect", "security": "Security"}

    def test_help_command(self):
        parsed = parse_input("/help", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "help"

    def test_quit_command(self):
        parsed = parse_input("/quit", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "quit"

    def test_new_command(self):
        parsed = parse_input("/new", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "new"

    def test_provider_with_args(self):
        parsed = parse_input("/provider vertex", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "provider"
        assert parsed.args == "vertex"

    def test_model_with_args(self):
        parsed = parse_input(
            "/model gemini-2.5-pro", self._workflows(), self._roles()
        )
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "model"
        assert parsed.args == "gemini-2.5-pro"

    def test_workflow_detection(self, workflows_dir):
        wfs = discover_workflows(workflows_dir)
        parsed = parse_input(
            "/commit fix the tests",
            wfs,
            {},
            workflows_dir=workflows_dir,
        )
        assert parsed.input_type == InputType.WORKFLOW
        assert parsed.workflow_name == "commit"
        assert parsed.args == "fix the tests"
        assert parsed.workflow_content is None  # Content loading deferred to handler

    def test_role_detection(self, agents_yaml):
        roles = discover_roles(agents_yaml)
        parsed = parse_input(
            "@security review the auth module",
            {},
            roles,
            agents_yaml=agents_yaml,
        )
        assert parsed.input_type == InputType.ROLE
        assert parsed.role_name == "security"
        assert parsed.args == "review the auth module"
        assert parsed.role_context is None  # Context loading deferred to handler

    def test_unknown_command_is_chat(self):
        parsed = parse_input("/unknown thing", self._workflows(), self._roles())
        assert parsed.input_type == InputType.CHAT

    def test_plain_chat(self):
        parsed = parse_input(
            "How do I fix this?", self._workflows(), self._roles()
        )
        assert parsed.input_type == InputType.CHAT

    def test_empty_input(self):
        parsed = parse_input("", self._workflows(), self._roles())
        assert parsed.input_type == InputType.CHAT

    def test_unknown_role_is_chat(self):
        parsed = parse_input(
            "@unknown check this", self._workflows(), self._roles()
        )
        assert parsed.input_type == InputType.CHAT

    def test_history_alias(self):
        """Verify /history resolves to canonical 'conversations' command."""
        parsed = parse_input("/history", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "conversations"

    def test_conversations_command(self):
        """Verify /conversations still works directly."""
        parsed = parse_input("/conversations", self._workflows(), self._roles())
        assert parsed.input_type == InputType.COMMAND
        assert parsed.command == "conversations"


class TestFormatHelp:
    def test_format_help_contains_commands(self):
        text = format_help_text(
            {"commit": "Commit changes"}, {"architect": "System Architect"}
        )
        assert "/help" in text
        assert "/quit" in text
        assert "/commit" in text
        assert "@architect" in text
