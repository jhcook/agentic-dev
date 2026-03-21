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
from typing import List, TypedDict

import yaml
from opentelemetry import trace
from rich.console import Console

from agent.core.config import config
from agent.core.utils import find_story_file, scrub_sensitive_data

console = Console()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Valid story states recognised by the agent workflow.
_VALID_STATES = frozenset({
    "DRAFT", "READY", "IN_PROGRESS", "COMMITTED", "DONE",
    "BLOCKED", "RETIRED", "DEPRECATED", "SUPERSEDED", "REVIEW_NEEDED",
})


def update_story_state(
    story_id: str,
    new_state: str,
    context_prefix: str = "",
    annotation: str = "",
) -> None:
    """Update the ``## State`` section of a Story markdown file and trigger a Notion sync.

    **Internal Use Only** — this is a CLI-level file-system utility, not an API endpoint.

    Called by:
        - ``agent commit`` (workflow.py) — sets state to ``COMMITTED``
        - ``agent implement`` (implement.py) — sets state to ``IN_PROGRESS``
        - ``agent decompose-story`` — sets state to ``SUPERSEDED`` with an annotation

    Args:
        story_id: The story identifier (e.g. ``INFRA-023``).
        new_state: Target state string (e.g. ``IN_PROGRESS``, ``COMMITTED``).
        context_prefix: Optional label for log output (e.g. ``Phase 0``, ``Post-Commit``).
        annotation: Optional suffix appended to the state token in the file,
            e.g. ``'(see plan: INFRA-157-plan.md)'``.  The full persisted value
            becomes ``'SUPERSEDED (see plan: INFRA-157-plan.md)'``.

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

    # Match the state heading followed by the current state token (which may
    # already include annotation text on the same line, e.g. "SUPERSEDED (…)").
    state_regex = r"(^## State\s*\n+)([^\n]+)"

    match = re.search(state_regex, content, re.MULTILINE)
    if not match:
        console.print(f"[yellow]⚠️  Could not find '## State' section in {story_file.name}[/yellow]")
        return

    current_state = match.group(2).strip()
    written_value = f"{new_state_upper} {annotation}".strip() if annotation else new_state_upper

    if current_state == written_value:
        return  # Already set (idempotent)

    new_content = re.sub(
        state_regex, f"\\1{written_value}", content, count=1, flags=re.MULTILINE
    )

    try:
        story_file.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write story file %s: %s", story_file, exc)
        console.print(f"[red]❌ Could not write {story_file}: {exc}[/red]")
        return

    console.print(
        f"[bold blue]🔄 {context_prefix}: Updated Story {story_id} "
        f"State: {current_state} -> {written_value}[/bold blue]"
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
    # Extract IDs already present in the section — check by ID, not full string,
    # so a title change never creates a duplicate (AC-5 idempotency).
    adr_section = content.split("## Linked ADRs")[1].split("##")[0] if "## Linked ADRs" in content else ""
    existing_adr_ids = set(re.findall(r"\bADR-\d+\b", adr_section))
    adrs_dir = getattr(config, "adrs_dir", None)
    if adrs_dir and Path(adrs_dir).exists():
        for adr_id in sorted(adrs):
            if adr_id in existing_adr_ids:
                continue  # already present — skip regardless of title
            matches = list(Path(adrs_dir).glob(f"{adr_id}*.md"))
            if matches:
                # Extract H1 title from ADR file; fall back to stem on parse failure
                try:
                    h1_match = re.search(r"^#\s+(.+)", matches[0].read_text(), re.MULTILINE)
                    title = h1_match.group(1).strip() if h1_match else matches[0].stem
                except OSError:
                    title = matches[0].stem
                resolved_adrs.append(f"- {adr_id}: {title}")
                adrs_added.append(adr_id)

    # --- Resolve Journey titles ----------------------------------------------
    resolved_journeys: list[str] = []
    # Same ID-based idempotency for journeys.
    jrn_section = content.split("## Linked Journeys")[1].split("##")[0] if "## Linked Journeys" in content else ""
    existing_jrn_ids = set(re.findall(r"\bJRN-\d+\b", jrn_section))
    journeys_dir = getattr(config, "journeys_dir", None)
    if journeys_dir and Path(journeys_dir).exists():
        for jrn_id in sorted(journeys):
            if jrn_id in existing_jrn_ids:
                continue  # already present
            num = jrn_id.split("-")[1]
            matches = list(Path(journeys_dir).rglob(f"JRN-{num}*.yaml"))
            if matches:
                # Try to read the name field from the YAML
                try:
                    data = yaml.safe_load(matches[0].read_text())
                    name = data.get("name", matches[0].stem) if isinstance(data, dict) else matches[0].stem
                except (yaml.YAMLError, OSError):
                    name = matches[0].stem
                resolved_journeys.append(f"- {jrn_id}: {name}")
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


# ---------------------------------------------------------------------------
# INFRA-159 — S/R block validation helpers
# ---------------------------------------------------------------------------


class SRMismatch(TypedDict):
    """A single S/R block that failed to match the target file on disk."""

    file: str
    """Relative path to the target file (as declared in the runbook header)."""
    search: str
    """The verbatim <<<SEARCH content that could not be found in the file."""
    actual: str
    """Full content of the target file at validation time."""
    index: int
    """1-based block counter within this file (for user-facing error messages)."""
    missing_modify: bool
    """True when a [MODIFY] block targets a file that does not yet exist on disk."""
    replace: str
    """The REPLACE content from the S/R block (useful for autohealing to [NEW])."""

def _lines_match(search_text: str, file_text: str) -> bool:
    """Return True if *search_text* exists as a contiguous block in *file_text*.

    Comparison is done line-by-line with trailing whitespace stripped per line
    to absorb minor AI formatting variance.

    Args:
        search_text: The block of text to look for (SEARCH block content).
        file_text: The full content of the target file on disk.

    Returns:
        True if every line of *search_text* appears contiguously in *file_text*.
    """
    search_lines = [line.rstrip() for line in search_text.splitlines()]
    file_lines = [line.rstrip() for line in file_text.splitlines()]

    if not search_lines:
        return True

    n = len(search_lines)
    for i in range(len(file_lines) - n + 1):
        if file_lines[i : i + n] == search_lines:
            return True
    return False


def validate_sr_blocks(content: str) -> List[SRMismatch]:
    """Validate every SEARCH block in a runbook against the target file on disk.

    Uses :func:`agent.core.implement.parser.parse_search_replace_blocks` to
    extract S/R blocks (reusing the canonical parser — no duplicated regex) and
    :func:`agent.core.implement.parser.extract_modify_files` to identify which
    operations require an existing file.

    Args:
        content: Full runbook markdown content.

    Returns:
        List of :class:`SRMismatch` typed dicts — each has keys ``file``,
        ``search``, ``actual``, and ``index`` (1-based block counter per file).

    Raises:
        FileNotFoundError: If a ``[MODIFY]`` block targets a file that does not
            exist on disk. ``[NEW]`` blocks targeting non-existent files are
            silently skipped (they will be created by ``agent implement``).
    """
    # Deferred imports to avoid circular dependency at module load time.
    from agent.core.implement.parser import (  # noqa: PLC0415
        parse_search_replace_blocks,
        extract_modify_files,
        _extract_runbook_data_ast,
    )
    from agent.core.implement.models import ParsingError  # noqa: PLC0415
    from agent.core.implement.resolver import resolve_path  # noqa: PLC0415

    # Files declared in [MODIFY] headers — missing files are an immediate error.
    # The parser now flags malformed blocks instead of crashing, but we still
    # guard against unexpected parse failures.
    try:
        modify_files: set[str] = set(extract_modify_files(content))
    except (ParsingError, ValueError) as pe:
        return [{"file": "PARSE_ERROR", "index": 0, "search": "", "actual": "",
                 "missing_modify": False, "parse_error": str(pe)}]

    # Detect malformed [MODIFY] blocks (header present, no S/R pairs).
    # The AST parser flags these with malformed=True instead of crashing.
    try:
        steps = _extract_runbook_data_ast(content)
    except (ParsingError, ValueError):
        steps = []
    malformed_mismatches: List[SRMismatch] = []
    for step in steps:
        for op in step.get("operations", []):
            if op.get("malformed") and "blocks" in op:
                malformed_mismatches.append({
                    "file": op["path"],
                    "index": 0,
                    "search": "",
                    "actual": "",
                    "missing_modify": False,
                    "parse_error": f"MODIFY header for '{op['path']}' has no valid SEARCH/REPLACE blocks",
                })

    # All S/R blocks (MODIFY + NEW that contain <<<SEARCH blocks).
    sr_blocks = parse_search_replace_blocks(content)

    mismatches: List[SRMismatch] = []
    # Track per-file block index (1-based).
    block_counters: dict[str, int] = {}

    for block in sr_blocks:
        file_path_str = block["file"]
        search_text = block["search"]

        abs_path = resolve_path(file_path_str)
        is_modify = file_path_str in modify_files

        # Meta-files in .agent/cache/ (stories, plans, runbooks) are managed
        # by agent commands — not source code. Skip validation silently.
        if ".agent/cache/" in file_path_str or "/.agent/cache/" in file_path_str:
            continue

        if is_modify and (abs_path is None or not abs_path.exists()):
            # Return a structured mismatch instead of raising — caller decides healing.
            mismatches.append(
                {
                    "file": file_path_str,
                    "search": block.get("search", ""),
                    "actual": "",
                    "index": block_counters.get(file_path_str, 0) + 1,
                    "missing_modify": True,
                    "replace": block.get("replace", ""),
                }
            )
            continue

        # [NEW] targeting a file that doesn't exist yet — nothing to match.
        if not is_modify and (abs_path is None or not abs_path.exists()):
            continue

        if abs_path is not None and abs_path.exists():
            block_counters[file_path_str] = block_counters.get(file_path_str, 0) + 1
            idx = block_counters[file_path_str]

            try:
                file_text = abs_path.read_text(encoding="utf-8")
            except OSError:
                continue  # unreadable — skip silently

            if not _lines_match(search_text, file_text):
                mismatches.append(
                    {
                        "file": file_path_str,
                        "search": search_text,
                        "actual": file_text,
                        "index": idx,
                        "missing_modify": False,
                        "replace": block.get("replace", ""),
                    }
                )

    return malformed_mismatches + mismatches


def generate_sr_correction_prompt(mismatches: List[SRMismatch]) -> str:
    """Build an AI correction prompt for failing S/R blocks.

    Handles two kinds of findings:
    - **Regular mismatches**: SEARCH text doesn't match the file.
    - **Parse errors**: MODIFY header present but no valid S/R blocks at all.

    File content is scrubbed with :func:`scrub_sensitive_data` before being
    embedded in the prompt (security requirement — no PII/secrets in AI calls).

    Args:
        mismatches: List of mismatch dicts returned by :func:`validate_sr_blocks`.

    Returns:
        Formatted instruction string ready to append to the AI user prompt.
    """
    # Separate structural errors from content mismatches
    parse_errors = [m for m in mismatches if m.get("parse_error")]
    content_mismatches = [m for m in mismatches if not m.get("parse_error")]

    lines = []

    if parse_errors:
        lines.append(
            "MALFORMED MODIFY BLOCKS. The following [MODIFY] headers have no valid "
            "<<<SEARCH/===/>>>REPLACE blocks. Each [MODIFY] MUST contain at least one "
            "<<<SEARCH block with exact content from the target file:\n"
        )
        for m in parse_errors:
            lines.append(f"FILE: {m['file']}")
            lines.append(f"ERROR: {m['parse_error']}")
            lines.append("---")
        lines.append(
            "\nInstruction: Rewrite the MODIFY sections listed above to include "
            "proper <<<SEARCH / === / >>>REPLACE blocks. The SEARCH text must be "
            "an exact verbatim excerpt from the actual file."
        )

    if content_mismatches:
        if lines:
            lines.append("\n")
        lines.append(
            "S/R VALIDATION FAILED. The following SEARCH blocks do not match the "
            "target files:\n"
        )
        for m in content_mismatches:
            lines.append(f"FILE: {m['file']} (Block #{m['index']})")
            lines.append(f"FAILING SEARCH BLOCK:\n{m['search']}\n")
            lines.append(
                f"ACTUAL FILE CONTENT FOR {m['file']}:\n"
                f"{scrub_sensitive_data(m['actual'])}"
            )
            lines.append("---")
        lines.append(
            "\nInstruction: Rewrite ONLY the failing MODIFY blocks listed above "
            "so that every <<<SEARCH block exactly matches the actual file content "
            "provided. Use the provided actual content verbatim. Output ONLY the "
            "corrected #### [MODIFY] sections — do NOT reproduce the rest of the runbook."
        )
    return "\n".join(lines)


def build_journey_catalogue(journeys_dir: Path) -> tuple[str, int]:
    """Build a sorted, capped catalogue of available Journeys for AI context.

    Scans the journeys directory recursively for YAML files, extracts the ID and
    title/name, and returns a formatted markdown list. Capped at 30 entries
    sorted by numeric ID descending.

    Args:
        journeys_dir: Path to the directory containing JRN-*.yaml files.

    Returns:
        A tuple of (formatted_catalogue_string, total_count_found).
    """
    with tracer.start_as_current_span("build_journey_catalogue") as span:
        if not journeys_dir.exists():
            logger.debug("Journeys directory missing: %s", journeys_dir)
            span.set_attribute("journey_count", 0)
            return "", 0

        entries: list[tuple[str, str]] = []
        for jf in journeys_dir.rglob("*.yaml"):
            try:
                data = yaml.safe_load(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    jid = data.get("id", jf.stem)
                    # Prefer 'title' per AC, fall back to 'name' or stem
                    title = data.get("title") or data.get("name") or jf.stem
                    entries.append((str(jid), str(title)))
            except Exception:  # noqa: BLE001
                continue

        if not entries:
            span.set_attribute("journey_count", 0)
            return "", 0

        total_count = len(entries)
        span.set_attribute("journey_count", total_count)

        # Sort by numeric ID descending: JRN-089 -> 89
        def sort_key(e: tuple[str, str]) -> int:
            match = re.search(r"(\d+)", e[0])
            return int(match.group(1)) if match else 0

        entries.sort(key=sort_key, reverse=True)
        top_30 = entries[:30]

        lines = ["Available Journeys:"]
        for jid, title in top_30:
            lines.append(f"- {jid}: {title}")
        return "\n".join(lines), total_count


def build_adr_catalogue(adrs_dir: Path) -> tuple[str, int]:
    """Build a sorted, capped catalogue of available ADRs for AI context.

    Scans the ADRs directory for markdown files, extracts the H1 title,
    and returns a formatted markdown list. Capped at 30 entries sorted by
    numeric ID descending.

    Args:
        adrs_dir: Path to the directory containing ADR-*.md files.

    Returns:
        A tuple of (formatted_catalogue_string, total_count_found).
    """
    with tracer.start_as_current_span("build_adr_catalogue") as span:
        if not adrs_dir.exists():
            logger.debug("ADRs directory missing: %s", adrs_dir)
            span.set_attribute("adr_count", 0)
            return "", 0

        entries: list[tuple[str, str]] = []
        for af in adrs_dir.glob("ADR-*.md"):
            try:
                content = af.read_text(encoding="utf-8")
                h1_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
                title = h1_match.group(1).strip() if h1_match else af.stem
                # Extract ID from filename (e.g. ADR-041)
                id_match = re.match(r"(ADR-\d+)", af.name)
                aid = id_match.group(1) if id_match else af.stem
                entries.append((str(aid), str(title)))
            except Exception:  # noqa: BLE001
                continue

        if not entries:
            span.set_attribute("adr_count", 0)
            return "", 0

        total_count = len(entries)
        span.set_attribute("adr_count", total_count)

        # Sort by numeric ID descending
        def sort_key(e: tuple[str, str]) -> int:
            match = re.search(r"(\d+)", e[0])
            return int(match.group(1)) if match else 0

        entries.sort(key=sort_key, reverse=True)
        top_30 = entries[:30]

        lines = ["Available ADRs:"]
        for aid, title in top_30:
            lines.append(f"- {aid}: {title}")
        return "\n".join(lines), total_count


# ---------------------------------------------------------------------------
# INFRA-161: DoD Compliance Gate helpers
# ---------------------------------------------------------------------------


def extract_acs(story_content: str) -> List[str]:
    """Extract Acceptance Criteria bullets from a story markdown file.

    Scans for the ``## Acceptance Criteria`` section and returns each
    non-empty bullet line (stripping leading ``- [ ]`` / ``- [x]`` markers).

    Args:
        story_content: Raw markdown text of the user story.

    Returns:
        List of AC strings.  Empty list if the section is absent.
    """
    import re as _re

    ac_section = _re.search(
        r"##\s+Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)",
        story_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    if not ac_section:
        return []
    raw = ac_section.group(1)
    acs: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _re.sub(r"^-\s*\[.\]\s*", "", stripped)
        cleaned = _re.sub(r"^[-*]\s+", "", cleaned)
        if cleaned:
            acs.append(cleaned)
    return acs


def build_ac_coverage_prompt(acs: List[str], runbook_content: str) -> str:
    """Build the secondary AI prompt for AC-1 coverage check.

    Asks the AI to identify which Acceptance Criteria from the story are NOT
    addressed by any step in the runbook.  The response format is strictly
    ``ALL_PASS`` (all covered) or one ``AC-N: <reason>`` line per gap.

    Args:
        acs: List of AC strings extracted from the parent story.
        runbook_content: Raw runbook markdown (implementation steps only).

    Returns:
        Prompt string to send to the AI for AC coverage analysis.
    """
    numbered = "\n".join(f"AC-{i + 1}: {ac}" for i, ac in enumerate(acs))
    # Trim runbook to the Implementation Steps section to keep prompt compact
    import re as _re
    impl_match = _re.search(
        r"#+\s*Implementation Steps?\s*\n(.*?)(?=\n#+|\Z)",
        runbook_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    steps_text = impl_match.group(1).strip() if impl_match else runbook_content[:4000]

    return (
        "You are a strict QA reviewer. Given the Acceptance Criteria (ACs) for a "
        "user story and the Implementation Steps in a runbook, identify which ACs "
        "are NOT addressed by any step in the runbook.\n\n"
        f"## Acceptance Criteria\n{numbered}\n\n"
        f"## Runbook Implementation Steps\n{steps_text}\n\n"
        "## Instructions\n"
        "Return ONLY one of:\n"
        "  • The literal string `ALL_PASS` if every AC is addressed.\n"
        "  • One line per unaddressed AC in the format `AC-N: <brief reason>`.\n"
        "Do NOT include any prose, preamble, or explanation outside this format."
    )


def parse_ac_gaps(ai_response: str) -> List[str]:
    """Parse the AI response from an AC coverage check.

    Args:
        ai_response: Raw string returned by the AI for AC coverage analysis.

    Returns:
        List of gap IDs (e.g. ``['AC-1', 'AC-3']``).  Empty list if all pass.
    """
    import re as _re

    text = ai_response.strip()
    if not text or "ALL_PASS" in text:
        return []
    gaps: List[str] = []
    for match in _re.finditer(r"^(AC-\d+):", text, _re.MULTILINE):
        gaps.append(match.group(1))
    return gaps


def check_test_coverage(runbook_content: str) -> List[str]:
    """Check that every ``[NEW]`` implementation file has a paired test file step.

    For each ``[NEW]`` non-test ``.py`` file found in the runbook, verifies that a
    corresponding ``[NEW]`` or ``[MODIFY]`` step targeting a ``test_<module>.py``
    (or ``<module>_test.py``) file also exists.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings — one per unpaired implementation file (empty if all pass).
    """
    import re as _re
    from pathlib import PurePosixPath

    pattern = _re.compile(
        r"####\s+\[(NEW|MODIFY)\]\s+([^\n]+)",
        _re.IGNORECASE,
    )

    # Source code extensions that DO need paired tests.
    # Everything else (config, docs, data, rules, templates, etc.) is excluded.
    _SOURCE_EXTS = {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php",
        ".c", ".cpp", ".h", ".hpp", ".cs",
    }
    # Boilerplate files that don't need paired tests
    _BOILERPLATE_STEMS = {"__init__", "conftest", "__main__", "setup"}

    impl_files: List[str] = []
    test_stems: set[str] = set()

    for m in pattern.finditer(runbook_content):
        action = m.group(1).upper()  # "NEW" or "MODIFY"
        path = m.group(2).strip()
        pp = PurePosixPath(path)
        stem = pp.stem  # filename without extension
        ext = pp.suffix.lower()

        # Only source code files need paired tests
        if ext not in _SOURCE_EXTS or stem in _BOILERPLATE_STEMS:
            continue

        # Detect test files by convention (language-agnostic: test_*, *_test, *.spec, *.test)
        is_test = (
            stem.startswith("test_")
            or stem.endswith("_test")
            or stem.endswith(".spec")
            or stem.endswith(".test")
        )

        if is_test:
            # Collect test stems from both NEW and MODIFY so existing test files count
            base = stem
            for prefix in ("test_",):
                if base.startswith(prefix):
                    base = base[len(prefix):]
            for suffix in ("_test", ".spec", ".test"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
            test_stems.add(base)
        elif action == "NEW":
            # Only NEW implementation files require a paired test step
            impl_files.append(path)

    gaps: List[str] = []
    for impl_path in impl_files:
        stem = PurePosixPath(impl_path).stem  # e.g. "search"
        if stem not in test_stems:
            gaps.append(
                f"[NEW] {impl_path} has no paired test file — "
                f"add a [NEW] or [MODIFY] step targeting a "
                f"test_{stem} file covering all public interfaces."
            )
    return gaps



def check_changelog_entry(runbook_content: str) -> List[str]:
    """Check that the runbook includes a CHANGELOG.md modification step.

    Uses a regex that looks specifically for a ``[MODIFY]`` or ``[NEW]``
    block header targeting ``CHANGELOG.md``, avoiding false positives from
    prose mentions of the word "CHANGELOG".

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re

    if _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+CHANGELOG\.md",
        runbook_content,
        _re.IGNORECASE,
    ):
        return []
    return [
        "No CHANGELOG.md step found — every story must document its change "
        "in CHANGELOG.md."
    ]


def check_license_headers(runbook_content: str) -> List[str]:
    """Check that every ``[NEW]`` source file step includes the project license header.

    Reads key phrases from ``.agent/templates/license_header.txt`` and verifies
    that each ``[NEW]`` source file block contains at least one of them.
    Falls back to checking for ``Copyright`` or ``LICENSE`` if the template
    is not found.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re
    from pathlib import Path, PurePosixPath

    # Non-source extensions that don't require license headers
    _NON_SOURCE_EXTS = {
        ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".html", ".css", ".csv", ".xml", ".svg", ".lock", ".env",
    }

    # Read key phrases from the license header template
    template_path = Path(".agent/templates/license_header.txt")
    if template_path.exists():
        template_text = template_path.read_text()
        # Extract the first non-empty line as the key phrase to check for
        key_phrases = [
            line.strip()
            for line in template_text.splitlines()
            if line.strip()
        ][:3]  # First 3 non-empty lines are enough to identify the header
    else:
        key_phrases = ["Copyright", "LICENSE"]

    gaps: List[str] = []
    new_file_pattern = _re.compile(
        r"####\s+\[NEW\]\s+([^\n]+)\s*\n+```[^\n]*\n(.*?)```",
        _re.DOTALL | _re.IGNORECASE,
    )
    for m in new_file_pattern.finditer(runbook_content):
        path = m.group(1).strip()
        ext = PurePosixPath(path).suffix.lower()
        if ext in _NON_SOURCE_EXTS:
            continue
        body = m.group(2)
        if not any(phrase in body for phrase in key_phrases):
            gaps.append(
                f"[NEW] {path} is missing the project license header "
                f"(from .agent/templates/license_header.txt). "
                "Add the license block at the top of the file."
            )
    return gaps


# ── Deterministic Auto-Fixes ─────────────────────────────────────────────── #
# These functions patch runbook content directly — no AI call required.        #
# ────────────────────────────────────────────────────────────────────────────── #

# Map file extensions to their comment prefix for license header injection.
_COMMENT_PREFIXES: dict[str, str] = {
    ".py": "# ", ".rb": "# ", ".sh": "# ", ".bash": "# ", ".zsh": "# ",
    ".yaml": "# ", ".yml": "# ", ".r": "# ", ".pl": "# ", ".pm": "# ",
    ".ts": "// ", ".js": "// ", ".tsx": "// ", ".jsx": "// ",
    ".go": "// ", ".rs": "// ", ".java": "// ", ".kt": "// ",
    ".c": "// ", ".cpp": "// ", ".h": "// ", ".hpp": "// ",
    ".cs": "// ", ".swift": "// ", ".scala": "// ", ".dart": "// ",
}


def auto_fix_license_headers(runbook_content: str) -> str:
    """Inject the project license header into ``[NEW]`` source file blocks.

    Reads the header from ``.agent/templates/license_header.txt``, wraps it
    with the appropriate comment prefix for the file's language, and prepends
    it to every ``[NEW]`` code block that is missing it.

    This is fully deterministic — no AI call is made.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Patched runbook content with license headers injected.
    """
    import re as _re
    from pathlib import Path, PurePosixPath

    _NON_SOURCE_EXTS = {
        ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".html", ".css", ".csv", ".xml", ".svg", ".lock", ".env",
    }

    template_path = Path(".agent/templates/license_header.txt")
    if not template_path.exists():
        return runbook_content  # nothing to inject

    raw_header = template_path.read_text().rstrip("\n")

    # Read key phrases for presence check (same as check_license_headers)
    key_phrases = [
        line.strip()
        for line in raw_header.splitlines()
        if line.strip()
    ][:3]

    new_file_pattern = _re.compile(
        r"(####\s+\[NEW\]\s+([^\n]+)\s*\n+)(```[^\n]*\n)(.*?```)",
        _re.DOTALL | _re.IGNORECASE,
    )

    def _inject(m: _re.Match) -> str:
        header_line = m.group(1)  # #### [NEW] path\n\n
        fence_open = m.group(3)    # ```lang\n
        body_and_close = m.group(4)  # code...```
        path = m.group(2).strip()

        ext = PurePosixPath(path).suffix.lower()
        if ext in _NON_SOURCE_EXTS:
            return m.group(0)

        # Already has the header?
        if any(phrase in body_and_close for phrase in key_phrases):
            return m.group(0)

        prefix = _COMMENT_PREFIXES.get(ext, "# ")
        formatted_header = "\n".join(
            f"{prefix}{line}".rstrip() for line in raw_header.splitlines()
        ) + "\n\n"

        return header_line + fence_open + formatted_header + body_and_close

    return new_file_pattern.sub(_inject, runbook_content)


def auto_fix_changelog_step(runbook_content: str) -> str:
    """Append a ``[MODIFY] CHANGELOG.md`` step if one is missing.

    This is fully deterministic — no AI call is made.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Patched runbook content with changelog step appended if needed.
    """
    import re as _re

    if _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+CHANGELOG\.md",
        runbook_content,
        _re.IGNORECASE,
    ):
        return runbook_content  # already present

    changelog_step = (
        "\n\n### Step N: Update CHANGELOG\n"
        "#### [MODIFY] CHANGELOG.md\n\n"
        "Add an entry under the `[Unreleased]` section documenting this change.\n"
    )
    return runbook_content.rstrip() + changelog_step


def check_otel_spans(runbook_content: str, story_content: str) -> List[str]:
    """Check that runbook steps touching commands/ or core/ include OTel spans.

    Only applies when the story explicitly mentions observability, tracing,
    or a new flow in commands/ or core/.

    Args:
        runbook_content: Raw runbook markdown.
        story_content: Raw story markdown (used to detect observability AC).

    Returns:
        List of gap strings (empty if requirement met or not applicable).
    """
    import re as _re

    otel_keywords = ("opentelemetry", "otel", "tracing", "span", "observability")
    if not any(kw in story_content.lower() for kw in otel_keywords):
        return []

    if "start_as_current_span" in runbook_content or "tracer.start" in runbook_content:
        return []

    touches_infra = _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+\.agent/src/agent/(commands|core)/",
        runbook_content,
        _re.IGNORECASE,
    )
    if touches_infra:
        return [
            "Story requires OTel observability but no 'start_as_current_span' / "
            "'tracer.start' found in runbook steps touching commands/ or core/. "
            "Add an OTel span for the new flow."
        ]
    return []


def build_dod_correction_prompt(
    gaps: List[str],
    story_content: str,
    acs: List[str],
) -> str:
    """Build a targeted correction prompt that bundles all DoD gaps.

    Args:
        gaps: List of gap description strings from the deterministic checkers.
        story_content: Scrubbed story text (for AC context).
        acs: Extracted acceptance criteria list.

    Returns:
        Formatted instruction string ready to append to the AI user prompt.
    """
    lines = [
        "DOD COMPLIANCE GATE FAILED. The following requirements are missing "
        "from the generated runbook:\n"
    ]
    for i, gap in enumerate(gaps, 1):
        lines.append(f"  {i}. {gap}")

    if acs:
        lines.append(
            "\nACCEPTANCE CRITERIA FROM STORY (ensure ALL are addressed by at "
            "least one Implementation Step):"
        )
        for ac in acs:
            lines.append(f"  - {ac}")

    lines.append(
        "\nInstruction: Regenerate the FULL runbook ensuring every gap above is "
        "resolved. Do not omit any existing correct steps — only add/fix the "
        "missing items. Return the complete updated runbook."
    )
    return "\n".join(lines)
