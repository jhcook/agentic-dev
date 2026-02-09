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

"""CLI-layer utility functions for agent commands."""

import logging
import re

from rich.console import Console

from agent.core.utils import find_story_file

console = Console()
logger = logging.getLogger(__name__)

# Valid story states recognised by the agent workflow.
_VALID_STATES = frozenset({
    "DRAFT", "READY", "IN_PROGRESS", "COMMITTED", "DONE",
    "BLOCKED", "RETIRED", "DEPRECATED", "SUPERSEDED",
})


def update_story_state(story_id: str, new_state: str, context_prefix: str = ""):
    """Update the ``## State`` section of a Story markdown file and trigger a Notion sync.

    **Internal Use Only** — this is a CLI-level file-system utility, not an API endpoint.

    Called by:
        - ``agent commit`` (workflow.py) — sets state to ``COMMITTED``
        - ``agent implement`` (implement.py) — sets state to ``IN_PROGRESS``

    Args:
        story_id: The story identifier (e.g. ``INFRA-023``).
        new_state: Target state string (e.g. ``IN_PROGRESS``, ``COMMITTED``).
        context_prefix: Optional label for log output (e.g. ``Phase 0``, ``Post-Commit``).

    Raises:
        ValueError: If *story_id* is empty or *new_state* is not a recognised state.
    """
    # --- Input validation ---------------------------------------------------
    if not story_id or not story_id.strip():
        raise ValueError("story_id must be a non-empty string")

    new_state_upper = new_state.strip().upper()
    if new_state_upper not in _VALID_STATES:
        raise ValueError(
            f"Invalid state '{new_state}'. Must be one of: {', '.join(sorted(_VALID_STATES))}"
        )

    story_file = find_story_file(story_id)
    if not story_file:
        console.print(f"[yellow]⚠️  Could not find Story {story_id} to update state.[/yellow]")
        return

    # --- File I/O with error handling ----------------------------------------
    try:
        content = story_file.read_text()
    except OSError as exc:
        logger.error("Failed to read story file %s: %s", story_file, exc)
        console.print(f"[red]❌ Could not read {story_file}: {exc}[/red]")
        return

    state_regex = r"(^## State\s*\n+)([A-Za-z_\s]+)"

    match = re.search(state_regex, content, re.MULTILINE)
    if not match:
        console.print(f"[yellow]⚠️  Could not find '## State' section in {story_file.name}[/yellow]")
        return

    current_state = match.group(2).strip()
    if current_state.upper() == new_state_upper:
        return  # Already set

    new_content = re.sub(
        state_regex, f"\\1{new_state_upper}", content, count=1, flags=re.MULTILINE
    )

    try:
        story_file.write_text(new_content)
    except OSError as exc:
        logger.error("Failed to write story file %s: %s", story_file, exc)
        console.print(f"[red]❌ Could not write {story_file}: {exc}[/red]")
        return

    console.print(
        f"[bold blue]🔄 {context_prefix}: Updated Story {story_id} "
        f"State: {current_state} -> {new_state_upper}[/bold blue]"
    )

    # --- Sync (non-fatal) ----------------------------------------------------
    try:
        from agent.sync.sync import push_safe
        push_safe(timeout=3, verbose=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notion sync failed after state update: %s", exc)

