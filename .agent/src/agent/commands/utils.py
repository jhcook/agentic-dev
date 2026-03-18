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
from rich.console import Console

from agent.core.config import config
from agent.core.utils import find_story_file, scrub_sensitive_data

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
    )
    from agent.core.implement.resolver import resolve_path  # noqa: PLC0415

    # Files declared in [MODIFY] headers — missing files are an immediate error.
    modify_files: set[str] = set(extract_modify_files(content))

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

        if is_modify and (abs_path is None or not abs_path.exists()):
            raise FileNotFoundError(
                f"[MODIFY] target does not exist on disk: {file_path_str}"
            )

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
                    }
                )

    return mismatches


def generate_sr_correction_prompt(mismatches: List[SRMismatch]) -> str:
    """Build an AI correction prompt for failing S/R blocks.

    File content is scrubbed with :func:`scrub_sensitive_data` before being
    embedded in the prompt (security requirement — no PII/secrets in AI calls).

    Args:
        mismatches: List of mismatch dicts returned by :func:`validate_sr_blocks`.

    Returns:
        Formatted instruction string ready to append to the AI user prompt.
    """
    lines = [
        "S/R VALIDATION FAILED. The following SEARCH blocks do not match the "
        "target files:\n"
    ]
    for m in mismatches:
        lines.append(f"FILE: {m['file']} (Block #{m['index']})")
        lines.append(f"FAILING SEARCH BLOCK:\n{m['search']}\n")
        lines.append(
            f"ACTUAL FILE CONTENT FOR {m['file']}:\n"
            f"{scrub_sensitive_data(m['actual'])}"
        )
        lines.append("---")
    lines.append(
        "\nInstruction: Rewrite the implementation steps so that EVERY "
        "<<<SEARCH block exactly matches the actual file content provided. "
        "Use the provided actual content verbatim. Return the FULL updated runbook."
    )
    return "\n".join(lines)


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


def check_test_coverage(runbook_content: str) -> List[str]:
    """Check that the runbook includes at least one test-file step.

    Looks for ``[NEW]`` or ``[MODIFY]`` blocks targeting paths that contain
    ``test_`` or ``_test.`` in the filename.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re

    pattern = _re.compile(
        r"####\s+\[(NEW|MODIFY)\]\s+([^\n]+)",
        _re.IGNORECASE,
    )
    for m in pattern.finditer(runbook_content):
        path = m.group(2).strip()
        filename = path.split("/")[-1]
        if "test_" in filename or "_test." in filename:
            return []
    return [
        "No test file step found — at least one [NEW] or [MODIFY] targeting "
        "a test_*.py file is required."
    ]


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
    """Check that every ``[NEW]`` Python file step includes the Apache-2.0 header.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    import re as _re

    gaps: List[str] = []
    new_py_pattern = _re.compile(
        r"####\s+\[NEW\]\s+([^\n]+\.py)\s*\n+```[^\n]*\n(.*?)```",
        _re.DOTALL | _re.IGNORECASE,
    )
    for m in new_py_pattern.finditer(runbook_content):
        path = m.group(1).strip()
        body = m.group(2)
        if "Copyright" not in body and "Apache" not in body and "LICENSE" not in body:
            gaps.append(
                f"[NEW] {path} is missing the Apache-2.0 license header. "
                "Add the standard copyright block at the top of the file."
            )
    return gaps


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
