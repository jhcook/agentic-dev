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

"""Console command dispatcher (INFRA-087).

Parses ``/command [args]`` patterns, ``/<workflow>`` prefixes,
and ``@<role>`` prefixes from user input.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Classification of user input."""

    COMMAND = "command"
    WORKFLOW = "workflow"
    ROLE = "role"
    CHAT = "chat"


@dataclass
class ParsedInput:
    """Result of parsing user input."""

    input_type: InputType
    command: Optional[str] = None  # e.g. "help", "quit", "new"
    args: Optional[str] = None  # remaining text after command/prefix
    workflow_name: Optional[str] = None
    workflow_content: Optional[str] = None
    role_name: Optional[str] = None
    role_context: Optional[str] = None
    raw: str = ""


# Built-in commands that are handled by the TUI directly
BUILTIN_COMMANDS = {
    "help", "quit", "new", "conversations", "history", "switch", "delete",
    "clear", "provider", "model", "rename", "search", "tools",
}

# Command aliases (alias -> canonical name)
COMMAND_ALIASES = {
    "history": "conversations",
}


def discover_workflows(workflows_dir: Path) -> Dict[str, str]:
    """Discover available workflows from the workflows directory.

    Returns:
        Dict mapping workflow name to its description.
    """
    workflows = {}
    if not workflows_dir.exists():
        return workflows

    for md_file in sorted(workflows_dir.glob("*.md")):
        name = md_file.stem
        description = ""
        try:
            content = md_file.read_text(encoding="utf-8")
            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    if isinstance(frontmatter, dict):
                        description = frontmatter.get("description", "")
        except Exception:
            pass
        workflows[name] = description
    return workflows


def discover_roles(agents_yaml: Path) -> Dict[str, str]:
    """Discover available roles from agents.yaml.

    Returns:
        Dict mapping role name to its description.
    """
    roles = {}
    if not agents_yaml.exists():
        return roles

    try:
        with open(agents_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and "team" in data:
            for entry in data["team"]:
                role = entry.get("role", "")
                desc = entry.get("description", "")
                if role:
                    roles[role] = desc
    except Exception:
        logger.warning("Failed to parse agents.yaml for role discovery")
    return roles


def load_workflow_content(workflows_dir: Path, workflow_name: str) -> Optional[str]:
    """Load the full markdown content of a workflow file."""
    path = workflows_dir / f"{workflow_name}.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def load_role_context(agents_yaml: Path, role_name: str) -> Optional[str]:
    """Load the role persona context from agents.yaml."""
    if not agents_yaml.exists():
        return None

    try:
        with open(agents_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and "team" in data:
            for entry in data["team"]:
                if entry.get("role", "").lower() == role_name.lower():
                    parts = [
                        f"Role: {entry.get('name', role_name)}",
                        f"Description: {entry.get('description', '')}",
                    ]
                    responsibilities = entry.get("responsibilities", [])
                    if responsibilities:
                        parts.append(
                            "Responsibilities:\n"
                            + "\n".join(f"  - {r}" for r in responsibilities)
                        )
                    checks = entry.get("governance_checks", [])
                    if checks:
                        parts.append(
                            "Governance Checks:\n"
                            + "\n".join(f"  - {c}" for c in checks)
                        )
                    instruction = entry.get("instruction", "")
                    if instruction:
                        parts.append(f"Instruction: {instruction}")
                    return "\n".join(parts)
    except Exception:
        pass
    return None


def parse_input(
    raw: str,
    known_workflows: Dict[str, str],
    known_roles: Dict[str, str],
    workflows_dir: Optional[Path] = None,
    agents_yaml: Optional[Path] = None,
) -> ParsedInput:
    """Parse user input into a structured command.

    Precedence:
      1. Built-in commands: ``/help``, ``/quit``, etc.
      2. Workflow invocation: ``/commit fix the tests``
      3. Role invocation: ``@security review the auth module``
      4. Plain chat message
    """
    text = raw.strip()
    if not text:
        return ParsedInput(input_type=InputType.CHAT, raw=raw)

    # Check for /command
    if text.startswith("/"):
        parts = text[1:].split(None, 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # Built-in commands
        if cmd in BUILTIN_COMMANDS:
            canonical = COMMAND_ALIASES.get(cmd, cmd)
            return ParsedInput(
                input_type=InputType.COMMAND,
                command=canonical,
                args=args,
                raw=raw,
            )

        # Workflow invocation
        if cmd in known_workflows:
            return ParsedInput(
                input_type=InputType.WORKFLOW,
                workflow_name=cmd,
                workflow_content=None,
                args=args,
                raw=raw,
            )

        # Unknown /command — treat as chat
        return ParsedInput(input_type=InputType.CHAT, raw=raw)

    # Check for @role
    if text.startswith("@"):
        parts = text[1:].split(None, 1)
        role = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if role in {r.lower() for r in known_roles}:
            return ParsedInput(
                input_type=InputType.ROLE,
                role_name=role,
                role_context=None,
                args=args,
                raw=raw,
            )

    # Plain chat
    return ParsedInput(input_type=InputType.CHAT, raw=raw)


def format_help_text(
    workflows: Dict[str, str], roles: Dict[str, str]
) -> str:
    """Format the /help output text."""
    lines = [
        "╭─── Console Commands ───╮",
        "",
        "  /help             Show this help message",
        "  /new              Start a new conversation",
        "  /conversations    List saved conversations",
        "  /history          Alias for /conversations",
        "  /switch <n>       Switch to conversation number n",
        "  /delete           Delete a conversation",
        "  /rename <title>   Rename current conversation",
        "  /clear            Clear the chat display",
        "  /provider [name]  Show/switch AI provider",
        "  /model [name]     Set model override",
        "  /tools            Show available agentic tools",
        "  /search <query>   Search output (n=next, r=reverse)",
        "  /copy             Copy chat to clipboard (or Ctrl+Y)",
        "  /quit             Exit the console",
        "",
        "╭─── Workflows ───╮",
        "",
    ]
    for name, desc in sorted(workflows.items()):
        lines.append(f"  /{name:<16} {desc}")

    lines.extend(["", "╭─── Roles ───╮", ""])
    for name, desc in sorted(roles.items()):
        lines.append(f"  @{name:<16} {desc}")

    lines.append("")
    lines.append("  Tab   Switch panels  │  ↑↓  History  │  n/r  Search nav")
    return "\n".join(lines)
