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
from pathlib import Path

import yaml
from rich.console import Console

from agent.core.config import config
from agent.core.utils import find_story_file

console = Console()
logger = logging.getLogger(__name__)

# Valid story states recognised by the agent workflow.
_VALID_STATES = frozenset({
    "DRAFT", "READY", "IN_PROGRESS", "COMMITTED", "DONE",
    "BLOCKED", "RETIRED", "DEPRECATED", "SUPERSEDED", "REVIEW_NEEDED",
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
        content = story_file.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to read story file %s: %s", story_file, exc)
        console.print(f"[red]❌ Could not read {story_file}: {exc}[/red]")
        return

    state_regex = r"(^## State\s*\n+)([A-Za-z_]+)"

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
        story_file.write_text(new_content, encoding="utf-8")
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


# ---------------------------------------------------------------------------
# Story link extraction helpers (INFRA-158)
# ---------------------------------------------------------------------------

def extract_adr_refs(text: str) -> set[str]:
    """Extract unique ADR-NNN references from a text string.

    Args:
        text: Runbook or other markdown content to scan.

    Returns:
        Deduplicated set of ADR identifiers, e.g. ``{"ADR-041", "ADR-025"}``.
    """
    return set(re.findall(r"\bADR-\d+\b", text))


def extract_journey_refs(text: str) -> set[str]:
    """Extract unique JRN-NNN references from a text string.

    Args:
        text: Runbook or other markdown content to scan.

    Returns:
        Deduplicated set of Journey identifiers, e.g. ``{"JRN-057"}``.
    """
    return set(re.findall(r"\bJRN-\d+\b", text))


def merge_story_links(
    story_file: Path,
    adrs: set[str],
    journeys: set[str],
) -> None:
    """Back-populate Linked ADRs and Linked Journeys sections in a story file.

    Only references that can be resolved to a local file are written.
    Unresolvable references are silently skipped so that ``agent implement``
    does not encounter dangling stubs.  Updates are idempotent.

    Args:
        story_file: Path to the story markdown file to update.
        adrs: Set of ADR identifiers extracted from the runbook.
        journeys: Set of Journey identifiers extracted from the runbook.
    """
    try:
        content = story_file.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("merge_story_links: cannot read %s: %s", story_file, exc)
        return

    adrs_added: list[str] = []
    journeys_added: list[str] = []

    # --- Resolve ADR titles --------------------------------------------------
    resolved_adrs: list[str] = []
    adrs_dir = getattr(config, "adrs_dir", None)
    if adrs_dir and Path(adrs_dir).exists():
        for adr_id in sorted(adrs):
            matches = list(Path(adrs_dir).glob(f"{adr_id}*.md"))
            if matches:
                # Extract H1 title from ADR file; fall back to stem on parse failure
                try:
                    h1_match = re.search(r"^#\s+(.+)", matches[0].read_text(), re.MULTILINE)
                    title = h1_match.group(1).strip() if h1_match else matches[0].stem
                except OSError:
                    title = matches[0].stem
                entry = f"- {adr_id}: {title}"
                if entry not in content:
                    resolved_adrs.append(entry)
                    adrs_added.append(adr_id)

    # --- Resolve Journey titles ----------------------------------------------
    resolved_journeys: list[str] = []
    journeys_dir = getattr(config, "journeys_dir", None)
    if journeys_dir and Path(journeys_dir).exists():
        for jrn_id in sorted(journeys):
            num = jrn_id.split("-")[1]
            matches = list(Path(journeys_dir).rglob(f"JRN-{num}*.yaml"))
            if matches:
                # Try to read the name field from the YAML
                try:
                    data = yaml.safe_load(matches[0].read_text())
                    name = data.get("name", matches[0].stem) if isinstance(data, dict) else matches[0].stem
                except (yaml.YAMLError, OSError):
                    name = matches[0].stem
                entry = f"- {jrn_id}: {name}"
                if entry not in content:
                    resolved_journeys.append(entry)
                    journeys_added.append(jrn_id)

    if not resolved_adrs and not resolved_journeys:
        return  # Nothing resolvable — leave story unchanged

    # --- Inject ADRs ---------------------------------------------------------
    if resolved_adrs:
        new_block = "\n".join(resolved_adrs)
        # Replace "- None" placeholder or append to existing list
        content = re.sub(
            r"(## Linked ADRs\s*\n+)- None",
            f"\\1{new_block}",
            content,
            count=1,
        )
        # If section already has entries, append after the last bullet
        if not any(a in content for a in resolved_adrs):
            content = re.sub(
                r"(## Linked ADRs\s*\n)((?:- .+\n)*)",
                f"\\1\\2{new_block}\n",
                content,
                count=1,
            )

    # --- Inject Journeys -----------------------------------------------------
    if resolved_journeys:
        new_block = "\n".join(resolved_journeys)
        content = re.sub(
            r"(## Linked Journeys\s*\n+)- None",
            f"\\1{new_block}",
            content,
            count=1,
        )
        if not any(j in content for j in resolved_journeys):
            content = re.sub(
                r"(## Linked Journeys\s*\n)((?:- .+\n)*)",
                f"\\1\\2{new_block}\n",
                content,
                count=1,
            )

    # --- Write atomically ----------------------------------------------------
    tmp = story_file.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(story_file)
        story_id = story_file.stem.split("-")[0] + "-" + story_file.stem.split("-")[1]
        logger.info(
            "story_links_updated",
            extra={"story_id": story_id, "adrs_added": adrs_added, "journeys_added": journeys_added},
        )
        console.print(
            f"[dim]📎 Back-populated story links — ADRs: {adrs_added or 'none'}, "
            f"Journeys: {journeys_added or 'none'}[/dim]"
        )
    except OSError as exc:
        logger.warning("merge_story_links: cannot write %s: %s", story_file, exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
