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

import ast
import logging
import re
from pathlib import Path
from typing import Dict, List, NotRequired, Optional, Set, TypedDict

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
    "DRAFT", "READY", "COMMITTED", "DONE",
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
        - ``agent implement`` (implement.py) — validates state is ``COMMITTED``
        - ``agent decompose-story`` — sets state to ``SUPERSEDED`` with an annotation

    Args:
        story_id: The story identifier (e.g. ``INFRA-023``).
        new_state: Target state string (e.g. ``COMMITTED``, ``DONE``).
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
                # 1. Try to read the name field from the YAML
                name = None
                try:
                    data = yaml.safe_load(matches[0].read_text())
                    if isinstance(data, dict):
                        name = data.get("name")
                except (yaml.YAMLError, OSError):
                    pass
                
                # Only add if a valid name was found in the YAML
                if name:
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
    with tracer.start_as_current_span(
        "merge_story_links_io",
        attributes={"story_file": str(story_file)}
    ) as span:
        tmp = story_file.with_suffix(".tmp")
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(story_file)
            
            story_id = story_file.stem.split("-")[0] + "-" + story_file.stem.split("-")[1]
            logger.info("story_links_updated", extra={
                "story_id": story_id,
                "adrs_added": adrs_added,
                "journeys_added": journeys_added,
            })
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
    # INFRA-180: optional keys populated by REPLACE-side semantic validation.
    replace_syntax_error: NotRequired[str]
    replace_import_error: NotRequired[str]
    replace_signature_error: NotRequired[str]
    replace_regression_warning: NotRequired[str]

# ---------------------------------------------------------------------------
# INFRA-180: REPLACE-side semantic validation helpers
# ---------------------------------------------------------------------------

_SR_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB — skip AST on oversized files


def _sr_check_replace_syntax(
    file_text: str, search_text: str, replace_text: str
) -> Optional[str]:
    """AC-1: Check that applying the REPLACE produces valid Python syntax.

    Only called for .py files. Operates entirely in-memory.
    """
    projected = file_text.replace(search_text, replace_text, 1)
    if len(projected.encode("utf-8")) > _SR_MAX_FILE_BYTES:
        return None  # Too large to parse safely — skip silently
    try:
        ast.parse(projected)
    except SyntaxError as e:
        logger.warning(
            "sr_replace_syntax_fail",
            extra={"error": e.msg, "line": e.lineno},
        )
        return f"Gate REPLACE-syntax: applying REPLACE to produces SyntaxError: {e.msg} at line {e.lineno}."
    return None


def _sr_check_replace_imports(
    replace_text: str, workspace_root: Path, other_defs: Set[str]
) -> Optional[str]:
    """AC-2: Verify that new 'from agent.X import Y' statements in REPLACE
    resolve to real symbols on disk or symbols defined in other runbook blocks.

    Only checks internal agent.* imports to avoid third-party false positives.
    """
    try:
        tree = ast.parse(replace_text)
    except SyntaxError:
        return None  # Syntax failures handled by AC-1

    unresolved: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if not module.startswith("agent."):
            continue  # Only validate internal imports
        # Map module path to filesystem path under workspace src/
        rel_path = Path(module.replace(".", "/") + ".py")
        candidate = workspace_root / ".agent" / "src" / rel_path
        for name_alias in node.names:
            sym = name_alias.name
            if sym in other_defs:
                continue  # Defined in a sibling runbook block
            if candidate.exists():
                try:
                    src = candidate.read_text(encoding="utf-8")
                    mod_tree = ast.parse(src)
                    defined = {
                        n.name
                        for n in ast.walk(mod_tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    }
                    # Also catch module-level assignments (e.g. SRMismatch = TypedDict(...))
                    defined |= {
                        n.targets[0].id
                        for n in ast.walk(mod_tree)
                        if isinstance(n, ast.Assign)
                        and len(n.targets) == 1
                        and isinstance(n.targets[0], ast.Name)
                    }
                    # Also catch re-exported symbols: `from X import Y` makes Y a public
                    # name in the module (e.g. check_projected_loc re-exported from loc_guard).
                    for imp_node in ast.walk(mod_tree):
                        if isinstance(imp_node, ast.ImportFrom):
                            for alias in imp_node.names:
                                defined.add(alias.asname or alias.name)
                    if sym not in defined:
                        unresolved.append(f"{module}.{sym}")
                except (OSError, SyntaxError):
                    pass  # Can't read or parse — skip conservatively
            else:
                unresolved.append(f"{module}.{sym}")

    if unresolved:
        logger.warning("sr_replace_import_fail", extra={"symbols": unresolved})
        return (
            f"Gate REPLACE-imports: REPLACE introduces unresolvable import(s): "
            f"{', '.join(unresolved)}. Verify the symbols exist or are created in another block."
        )
    return None


def _sr_check_replace_signature(
    search_text: str, replace_text: str, file_path: str
) -> Optional[str]:
    """AC-3: Detect public function/method signature regressions in REPLACE.

    Parses both SEARCH and REPLACE as Python snippets and compares arg lists
    for public functions (names that do not start with '_').
    """
    try:
        s_tree = ast.parse(search_text)
        r_tree = ast.parse(replace_text)
    except SyntaxError:
        return None  # Syntax failures handled by AC-1

    def _extract_sigs(tree: ast.AST) -> Dict[str, List[str]]:
        return {
            node.name: [a.arg for a in node.args.args]
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }

    s_sigs = _extract_sigs(s_tree)
    r_sigs = _extract_sigs(r_tree)

    for name, s_args in s_sigs.items():
        if name not in r_sigs:
            continue  # Function removed — handled by rename gate (INFRA-179)
        r_args = r_sigs[name]
        if s_args != r_args:
            logger.warning(
                "sr_replace_signature_fail",
                extra={"file": file_path, "function": name, "old": s_args, "new": r_args},
            )
            return (
                f"Gate REPLACE-signature: '{name}' in '{file_path}' has signature "
                f"{s_args} in SEARCH but {r_args} in REPLACE. "
                f"Ensure all callers are updated in this runbook."
            )
    return None


def _sr_check_replace_regression(
    search_text: str, replace_text: str, file_path: str
) -> Optional[str]:
    """AC-4 / AC-7: Warn when REPLACE is < sr_stub_threshold of SEARCH LOC.

    Intentional full deletions (empty REPLACE) are exempt per AC-7.
    """
    if not replace_text.strip():
        return None  # AC-7: intentional deletion, exempt

    threshold = getattr(config, "sr_stub_threshold", 0.25)
    if threshold <= 0:
        return None

    s_loc = sum(1 for ln in search_text.splitlines() if ln.strip())
    r_loc = sum(1 for ln in replace_text.splitlines() if ln.strip())

    if s_loc > 0 and r_loc < s_loc * threshold:
        logger.warning(
            "sr_replace_regression_warn",
            extra={"file": file_path, "search_loc": s_loc, "replace_loc": r_loc},
        )
        return (
            f"Gate REPLACE-regression: REPLACE for '{file_path}' is {r_loc} LOC "
            f"versus {s_loc} LOC in SEARCH ({r_loc/s_loc:.0%}). "
            f"Possible AI stub regression — ensure the full implementation is present."
        )
    return None


def _lines_match(search_text: str, file_text: str) -> bool:
    """Return True if *search_text* exists as a contiguous block in *file_text*.

    Each line is fully stripped (leading + trailing whitespace) before
    comparison to absorb AI indentation drift.

    Args:
        search_text: The block of text to look for (SEARCH block content).\n        file_text: The full content of the target file on disk.

    Returns:
        True if every line of *search_text* appears contiguously in *file_text*.
    """
    search_lines = [line.strip() for line in search_text.splitlines()]
    file_lines = [line.strip() for line in file_text.splitlines()]

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
        When a SEARCH match is found, REPLACE-side semantic checks (INFRA-180)
        are applied and failures are reported as optional keys on the same dict:
        ``replace_syntax_error``, ``replace_import_error``,
        ``replace_signature_error``, and ``replace_regression_warning``.

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

    # Build cross-block symbol index so _sr_check_replace_imports can skip symbols
    # that are defined in sibling [NEW]/[MODIFY] blocks of this runbook.
    #
    # Strategy: scan the ENTIRE content string once with a regex. This is simpler
    # and more robust than trying to extract individual "replace" fields from SR
    # block dicts — those fields can be empty when multiple SR blocks live in separate
    # fenced code fences under the same [MODIFY] header (a parser edge case).
    # Scanning the full content is intentionally broad (includes SEARCH text), but
    # false positives in an allowlist are harmless; false negatives break generation.
    _session_other_defs: Set[str] = set(
        re.findall(
            r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
            content,
            re.MULTILINE,
        )
    )

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

            replace_text = block.get("replace", "")
            if not _lines_match(search_text, file_text):
                mismatches.append(
                    {
                        "file": file_path_str,
                        "search": search_text,
                        "actual": file_text,
                        "index": idx,
                        "missing_modify": False,
                        "replace": replace_text,
                    }
                )
            else:
                # SEARCH matched — now validate the REPLACE side (INFRA-180)
                is_py = file_path_str.endswith(".py")
                sem_errors: Dict[str, str] = {}

                if is_py and getattr(config, "sr_check_syntax", True):
                    err = _sr_check_replace_syntax(file_text, search_text, replace_text)
                    if err:
                        sem_errors["replace_syntax_error"] = err

                if is_py and not sem_errors and getattr(config, "sr_check_imports", True):
                    err = _sr_check_replace_imports(replace_text, config.repo_root, _session_other_defs)
                    if err:
                        sem_errors["replace_import_error"] = err

                if is_py and getattr(config, "sr_check_signatures", True):
                    err = _sr_check_replace_signature(search_text, replace_text, file_path_str)
                    if err:
                        sem_errors["replace_signature_error"] = err

                if getattr(config, "sr_stub_threshold", 0.25) > 0:
                    err = _sr_check_replace_regression(search_text, replace_text, file_path_str)
                    if err:
                        sem_errors["replace_regression_warning"] = err

                if sem_errors:
                    mismatches.append(
                        {
                            "file": file_path_str,
                            "search": search_text,
                            "actual": file_text,
                            "index": idx,
                            "missing_modify": False,
                            "replace": replace_text,
                            **sem_errors,
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





# ---------------------------------------------------------------------------
# INFRA-161: DoD Compliance Gate helpers
# Extracted to agent.commands.dod_checks (INFRA-165) — re-exported here for
# backward compatibility.
# ---------------------------------------------------------------------------

from agent.commands.dod_checks import (  # noqa: F401
    auto_fix_changelog_step,
    auto_fix_license_headers,
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    parse_ac_gaps,
)

