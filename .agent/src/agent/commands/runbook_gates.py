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

"""Runbook generation gate loop.

Extracted from ``runbook.py`` to keep module LOC under the quality gate.
Contains the schema, code, S/R, and DoD gates that run after AI generation,
plus the retry/correction logic that sends combined fixes back to the AI.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import typer
from opentelemetry import trace
from rich.console import Console

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data
from agent.commands.utils import (
    auto_fix_changelog_step,
    auto_fix_license_headers,
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    generate_sr_correction_prompt,
    parse_ac_gaps,
    validate_sr_blocks,
)
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
    check_test_imports_resolvable,
    check_api_surface_renames,
)
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.core.implement.parser import detect_malformed_modify_blocks, parse_code_blocks, parse_search_replace_blocks
from agent.utils.validation_formatter import format_runbook_errors

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()
error_console = Console(stderr=True)


def _build_runbook_symbol_index(content: str) -> Set[str]:
    """Extract a set of top-level symbol names from all [NEW] code blocks in the runbook.

    Used by Gate 3.7 to resolve cross-block imports so that a test file importing
    a class defined earlier in the same runbook does not trigger a false positive.

    Args:
        content: The raw runbook markdown string.

    Returns:
        A set of symbol names (class names, function names, variable names) defined
        in any [NEW] block in the runbook.
    """
    import ast as _ast

    symbols: Set[str] = set()
    for block in parse_code_blocks(content):
        try:
            tree = _ast.parse(block.get("content", ""))
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)):
                symbols.add(node.name)
            elif isinstance(node, _ast.Assign):
                for t in node.targets:
                    if isinstance(t, _ast.Name):
                        symbols.add(t.id)
    return symbols


def run_generation_gates(
    content: str,
    story_id: str,
    story_content: str,
    user_prompt: str,
    system_prompt: str,
    known_new_files: Set[str],
    attempt: int,
    max_attempts: int,
    gate_corrections: int,
    max_gate_corrections: int,
) -> Tuple[str, List[str], int, Set[str], int]:
    """Run ALL validation gates on generated runbook content.

    This function runs every gate in collect mode — no short-circuiting.
    If any gate fails, it returns a combined correction prompt for the AI.

    Args:
        content: The generated runbook markdown.
        story_id: The story identifier.
        story_content: Full content of the user story.
        user_prompt: The current user prompt (for reconstruction).
        system_prompt: The system prompt (for S/R targeted fix calls).
        known_new_files: Files known to not exist yet.
        attempt: Current attempt number.
        max_attempts: Maximum number of attempts.
        gate_corrections: Current number of gate corrections consumed.
        max_gate_corrections: Maximum gate corrections allowed.

    Returns:
        Tuple of (content, correction_parts, gate_corrections, known_new_files, attempt_delta).
        If correction_parts is non-empty, the caller should retry.
        attempt_delta indicates how much to adjust the attempt counter.
    """
    correction_parts: List[str] = []
    attempt_delta = 0

    # 0. Projected LOC gate (INFRA-177) — runs before schema for fast feedback.
    # check_projected_loc parses NEW + MODIFY blocks from content internally.
    with tracer.start_as_current_span("projected_loc_gate") as loc_span:
        loc_errors = check_projected_loc(content, config.repo_root)
        loc_span.set_attribute("validation.passed", not bool(loc_errors))
        loc_span.set_attribute("validation.error_count", len(loc_errors))

    if loc_errors:
        logger.warning("projected_loc_gate_fail", extra={"story_id": story_id, "errors": loc_errors})
        correction_parts.append(
            "LOC GATE VIOLATIONS (Gate 0):\n"
            + "\n".join(f"- {e}" for e in loc_errors)
        )

    # 1. Schema validation
    with tracer.start_as_current_span("validate_runbook_schema") as span:
        schema_violations = validate_runbook_schema(content)
        span.set_attribute("validation.passed", not bool(schema_violations))
        span.set_attribute("validation.error_count", len(schema_violations) if schema_violations else 0)

    if schema_violations:
        logger.warning("runbook_schema_fail", extra={"attempt": attempt, "story_id": story_id})
        correction_parts.append(
            format_runbook_errors(schema_violations) + "\nPlease fix these schema errors."
        )

    # 1b. Malformed [MODIFY] block detection (AC-6 — INFRA-177)
    # detect_malformed_modify_blocks finds [MODIFY] headers that have a fenced
    # code block but are missing <<<SEARCH/===/>>> markers — these are silently
    # unreachable and indicate the AI forgot the S/R syntax.
    with tracer.start_as_current_span("malformed_modify_gate") as mal_span:
        malformed_paths = detect_malformed_modify_blocks(content)
        mal_span.set_attribute("validation.passed", not bool(malformed_paths))
        mal_span.set_attribute("validation.malformed_count", len(malformed_paths))

    if malformed_paths:
        logger.warning(
            "malformed_modify_block_gate",
            extra={"story_id": story_id, "files": malformed_paths},
        )
        detail = "\n".join(f"  - {p}" for p in malformed_paths)
        correction_parts.append(
            "MALFORMED [MODIFY] BLOCKS (Gate 1b):\n"
            f"{detail}\n"
            "Each listed [MODIFY] block has a fenced code block but is missing "
            "<<<SEARCH/===/>>> markers. Replace the fenced block with a proper "
            "<<<SEARCH ... === ... >>> diff."
        )

    # Gate 1c: API Surface Rename Detection (INFRA-179)
    with tracer.start_as_current_span("api_rename_gate") as rename_span:
        sr_blocks_for_rename: List[Dict[str, str]] = parse_search_replace_blocks(content)
        rename_span.set_attribute("gate1c.block_count", len(sr_blocks_for_rename))
        rename_errors = check_api_surface_renames(sr_blocks_for_rename, config.repo_root)
        rename_span.set_attribute("gate1c.corrections", len(rename_errors))
        if rename_errors:
            logger.warning(
                "api_rename_gate_fail",
                extra={"story_id": story_id, "errors": rename_errors},
            )
            for err in rename_errors:
                correction_parts.append(
                    f"API RENAME GATE (Gate 1c):\n{err}\n"
                    "Add [MODIFY] blocks for all consumer files, or revert the rename."
                )

    # 2. Code Gate Self-Healing (INFRA-155 AC-1)
    code_errors: List[str] = []
    code_warnings: List[str] = []

    with tracer.start_as_current_span("validate_code_gates") as span:
        parsed_blocks = parse_code_blocks(content)
        for b in parsed_blocks:
            res = validate_code_block(b["file"], b["content"])
            code_errors.extend(res.errors)
            code_warnings.extend(res.warnings)

        span.set_attribute("validation.passed", not bool(code_errors))
        span.set_attribute("validation.error_count", len(code_errors))

    # Gate 3.5: Projected Syntax Validation for [MODIFY] S/R blocks (AC-1 to AC-6)
    with tracer.start_as_current_span("validate_projected_syntax_gate") as syn_span:
        sr_blocks: List[Dict[str, str]] = parse_search_replace_blocks(content)
        syn_span.set_attribute("gate35.block_count", len(sr_blocks))
        for block in sr_blocks:
            syntax_err: Optional[str] = check_projected_syntax(
                config.repo_root / block["file"],
                block.get("search", ""),
                block.get("replace", ""),
                root_dir=config.repo_root,
            )
            if syntax_err:
                correction_parts.append(syntax_err)
        syn_span.set_attribute("gate35.corrections", len(correction_parts))

    # Gate 3.7: Test Import Resolution Guard (INFRA-178)
    with tracer.start_as_current_span("import_resolution_gate") as import_span:
        import_span.set_attribute("story_id", story_id)
        session_symbols = _build_runbook_symbol_index(content)
        new_blocks = [(b["file"], b["content"]) for b in parse_code_blocks(content)]
        test_block_count = sum(1 for f, _ in new_blocks if "test" in f or Path(f).name.startswith("test_"))
        import_span.set_attribute("gate37.test_block_count", test_block_count)
        for file_path, block_content in new_blocks:
            import_err = check_test_imports_resolvable(
                Path(file_path), block_content, session_symbols
            )
            if import_err:
                lookup_key = "IMPORT RESOLUTION FAILURE"
                correction_parts.append(
                    f"{lookup_key}\n"
                    f"Gate 3.7 detected unresolvable imports in `{file_path}`:\n"
                    f"{import_err}\n"
                    "Ensure every symbol imported in test files is either:\n"
                    "  a) A Python standard library module\n"
                    "  b) An installed package (present in the environment)\n"
                    "  c) Defined in a #### [NEW] block earlier in THIS runbook"
                )
        import_span.set_attribute("gate37.corrections", len(correction_parts))

    if code_errors:
        logger.warning("runbook_code_gate_fail", extra={"attempt": attempt, "story_id": story_id, "errors": code_errors})
        correction_parts.append(
            "CODE GATE VIOLATIONS:\n" + "\n".join(f"- {e}" for e in code_errors)
        )

    # 3. S/R Validation Gate (INFRA-159 + autohealing pre-pass)
    with tracer.start_as_current_span("sr_validation_gate") as sr_span:
        sr_span.set_attribute("story_id", story_id)
        sr_span.set_attribute("attempt", attempt)
        sr_mismatches = validate_sr_blocks(content)

        # Pre-pass: deterministically handle [MODIFY] on missing files.
        missing_blocks = [m for m in sr_mismatches if m.get("missing_modify")]
        real_mismatches = [m for m in sr_mismatches if not m.get("missing_modify")]

        if missing_blocks:
            logger.warning("sr_modify_missing", extra={"story_id": story_id, "count": len(missing_blocks)})
            missing_paths = [m["file"] for m in missing_blocks]
            known_new_files.update(missing_paths)
            sr_span.set_attribute("outcome", "modify_missing_prepass")
            console.print(f"[yellow]⚠️  [MODIFY] on non-existent file(s): {missing_paths} — autohealing (free pass)...[/yellow]")
            missing_detail = "\n".join(
                f"  - {m['file']}: file does not exist, must use [NEW] with a full code block"
                for m in missing_blocks
            )
            correction_parts.append(
                "AUTOHEALING REQUIRED — [MODIFY] used for files that do not yet exist:\n"
                f"{missing_detail}\n"
                "For each listed file: replace `#### [MODIFY] <path>` + "
                "`<<<SEARCH/===/>>>` with `#### [NEW] <path>` followed by "
                "a complete fenced code block of the full intended file contents."
            )
            attempt_delta -= 1

        sr_span.set_attribute("mismatch_count", len(real_mismatches))

        if real_mismatches:
            logger.warning(
                "sr_validation_fail",
                extra={"attempt": attempt, "story_id": story_id, "count": len(real_mismatches),
                       "files": [m["file"] for m in real_mismatches]},
            )
            sr_span.set_attribute("outcome", "mismatch")

            # ── Targeted S/R fix: patch blocks in-place ──────────── #
            sr_prompt = generate_sr_correction_prompt(real_mismatches)
            console.print(f"[yellow]⚠️  S/R mismatch in {len(real_mismatches)} file(s) — targeted fix...[/yellow]")
            sr_fix = ai_service.complete(
                system_prompt=(
                    "You are a code correction assistant. Output ONLY the corrected "
                    "#### [MODIFY] sections with <<<SEARCH / === / >>>REPLACE blocks. "
                    "No prose, no explanation, no other content."
                ),
                user_prompt=sr_prompt,
            )
            if sr_fix:
                import re as _sr_re
                patched_any = False
                for m in real_mismatches:
                    old_search = m["search"].strip()
                    if old_search and old_search in content:
                        file_pattern = _sr_re.compile(
                            r"####\s+\[MODIFY\]\s+" + _sr_re.escape(m["file"]) + r".*?(?=####\s+\[|$)",
                            _sr_re.DOTALL,
                        )
                        fix_match = file_pattern.search(sr_fix)
                        if fix_match:
                            old_block = file_pattern.search(content)
                            if old_block:
                                content = content[:old_block.start()] + fix_match.group() + content[old_block.end():]
                                patched_any = True
                if patched_any:
                    logger.info("sr_targeted_fix_applied", extra={"story_id": story_id, "files": [m["file"] for m in real_mismatches]})
                    gate_corrections += 1
                    attempt_delta -= 1
                    return content, ["__SR_PATCHED__"], gate_corrections, known_new_files, attempt_delta
                else:
                    logger.warning("sr_targeted_fix_failed_fallback", extra={"story_id": story_id})
                    correction_parts.append(sr_prompt)
        elif not missing_blocks:
            if attempt > 1:
                sr_span.set_attribute("outcome", "corrected")
                logger.info("sr_correction_success", extra={"story_id": story_id, "attempt": attempt})
            else:
                sr_span.set_attribute("outcome", "pass")
            logger.info("sr_validation_pass", extra={"story_id": story_id})

    return content, correction_parts, gate_corrections, known_new_files, attempt_delta


def run_dod_gate(
    content: str,
    story_id: str,
    story_content: str,
    attempt: int,
    gate_corrections: int,
    max_gate_corrections: int,
) -> Tuple[str, List[str], int, bool]:
    """Run the DoD compliance gate on generated runbook content.

    Args:
        content: The generated runbook markdown.
        story_id: The story identifier.
        story_content: Full content of the user story.
        attempt: Current attempt number.
        gate_corrections: Current number of gate corrections consumed.
        max_gate_corrections: Maximum gate corrections allowed.

    Returns:
        Tuple of (content, dod_gaps, gate_corrections, patched).
        If dod_gaps is non-empty and patched is False, the gate failed terminally.
    """
    # Apply deterministic auto-fixes first
    content = auto_fix_license_headers(content)
    content = auto_fix_changelog_step(content)

    with tracer.start_as_current_span("dod_compliance_gate") as dod_span:
        dod_span.set_attribute("story_id", story_id)
        dod_span.set_attribute("attempt", attempt)
        acs = extract_acs(story_content)

        # AC-1: Secondary AI call — AC coverage check
        _gap_4a: List[str] = []
        if acs:
            _ac_prompt = build_ac_coverage_prompt(acs, content)
            _ac_response = ai_service.complete(
                system_prompt=(
                    "You are a QA reviewer. Respond ONLY with ALL_PASS or "
                    "AC-N: <reason> lines. No prose."
                ),
                user_prompt=scrub_sensitive_data(_ac_prompt),
            )
            _ac_gap_ids = parse_ac_gaps(_ac_response or "")
            if _ac_gap_ids:
                _gap_4a = [
                    f"AC coverage gap: {gid} is not addressed by any runbook step"
                    for gid in _ac_gap_ids
                ]

        # AC-2 through AC-5: Deterministic checks
        _gap_4b = check_test_coverage(content)
        _gap_4c = check_changelog_entry(content)
        _gap_4d = check_license_headers(content)
        _gap_4e = check_otel_spans(content, story_content)
        _gap_4f = check_impact_analysis_completeness(content)
        _gap_4g = check_adr_refs(content, config.adrs_dir)
        _gap_4i = check_stub_implementations(content)
        dod_gaps: List[str] = [
            *_gap_4a, *_gap_4b, *_gap_4c, *_gap_4d, *_gap_4e, *_gap_4f, *_gap_4g, *_gap_4i
        ]

        # Gap ID tracking for OTel
        _gap_ids_list: List[str] = []
        if _gap_4a:
            _gap_ids_list.append("4a")
        if _gap_4b:
            _gap_ids_list.append("4b")
        if _gap_4c:
            _gap_ids_list.append("4c")
        if _gap_4d:
            _gap_ids_list.append("4d")
        if _gap_4e:
            _gap_ids_list.append("4e")
        if _gap_4f:
            _gap_ids_list.append("4f")
        if _gap_4g:
            _gap_ids_list.append("4g")
        if _gap_4i:
            _gap_ids_list.append("4i")
        dod_span.set_attribute("gap_count", len(dod_gaps))
        dod_span.set_attribute("gaps", ",".join(_gap_ids_list))

    if not dod_gaps:
        return content, [], gate_corrections, True

    logger.warning(
        "dod_compliance_fail",
        extra={"attempt": attempt, "story_id": story_id, "gaps": dod_gaps},
    )

    gate_corrections += 1
    if gate_corrections > max_gate_corrections:
        logger.error("gate_corrections_exhausted", extra={"story_id": story_id, "gate_corrections": gate_corrections})
        error_console.print(f"[bold red]❌ Gate corrections exhausted ({max_gate_corrections} corrections).[/bold red]")
        for gap in dod_gaps[:5]:
            error_console.print(f"  [red]• {gap[:200]}[/red]")
        raise typer.Exit(code=1)

    issues = len(dod_gaps)
    console.print(f"[yellow]⚠️  Attempt {attempt}: DoD gate {issues} gap(s) — patching...[/yellow]")
    logger.info("dod_targeted_patch", extra={"attempt": attempt, "story_id": story_id, "test_gaps": len([g for g in dod_gaps if "has no paired test file" in g]), "other_gaps": len([g for g in dod_gaps if "has no paired test file" not in g])})

    patched = False

    # Targeted fix for missing test files
    test_gaps = [g for g in dod_gaps if "has no paired test file" in g]
    other_gaps = [g for g in dod_gaps if "has no paired test file" not in g]

    if test_gaps:
        import re as _gap_re
        impl_paths = []
        for g in test_gaps:
            m = _gap_re.match(r"\[NEW\]\s+(\S+)", g)
            if m:
                impl_paths.append(m.group(1))

        if impl_paths:
            test_prompt = (
                "Generate ONLY the following test file implementation steps "
                "to append to an existing runbook. For each file below, produce "
                "a step with #### [NEW] <test_path> and a fenced code block. "
                "Include the project license header at the top of each file.\n\n"
                "Files needing paired test files:\n"
                + "\n".join(f"  - {p}" for p in impl_paths)
                + "\n\nReturn ONLY the markdown steps, nothing else."
            )
            test_blocks = ai_service.complete(
                system_prompt="You are a code generation assistant. Output only markdown. No prose.",
                user_prompt=test_prompt,
            )
            if test_blocks:
                content = content.rstrip() + "\n\n" + test_blocks.strip() + "\n"
                content = auto_fix_license_headers(content)
                patched = True
                logger.info("test_blocks_appended", extra={"story_id": story_id, "count": len(impl_paths)})

    # For non-test gaps, build a targeted correction and append
    if other_gaps:
        dod_correction = build_dod_correction_prompt(other_gaps, story_content, acs)
        other_prompt = (
            "The following DoD gaps must be fixed. Generate ONLY the additional "
            "runbook steps needed to address them. Do NOT reproduce any existing "
            "content — output only NEW steps to append.\n\n"
            + dod_correction
        )
        other_blocks = ai_service.complete(
            system_prompt="You are a code generation assistant. Output only markdown. No prose.",
            user_prompt=other_prompt,
        )
        if other_blocks:
            content = content.rstrip() + "\n\n" + other_blocks.strip() + "\n"
            patched = True

    if not patched:
        logger.error("dod_patch_failed", extra={"story_id": story_id, "attempt": attempt})
        logger.error("dod_gate_exhausted", extra={"story_id": story_id, "gate_corrections": gate_corrections})
        error_console.print(f"[bold red]❌ DoD gate failed after {gate_corrections} corrections.[/bold red]")
        for gap in dod_gaps[:5]:
            error_console.print(f"  [red]• {gap[:200]}[/red]")
        raise typer.Exit(code=1)

    return content, dod_gaps, gate_corrections, patched


def handle_split_request(
    content: str,
    story_id: str,
    story_content: str,
    story_file: Path,
    skip_forecast: bool,
) -> None:
    """Handle a SPLIT_REQUEST response from the AI.

    Args:
        content: The AI response containing the split request JSON.
        story_id: The story identifier.
        story_content: Full content of the user story.
        story_file: Path to the story file.
        skip_forecast: Whether forecast was skipped.
    """
    import json

    split_data = parse_split_request(content)
    if split_data:
        est_loc = split_data.get("estimated_loc")
        est_files = split_data.get("estimated_files")
        logger.warning(
            "ai_split_request",
            extra={
                "story_id": story_id,
                "reason": split_data.get("reason", ""),
                "estimated_loc": est_loc,
                "estimated_files": est_files,
            },
        )
        # Generate the decomposition plan for the user
        from agent.commands.runbook_helpers import generate_decomposition_plan
        plan_path = generate_decomposition_plan(story_id, story_content)
        console.print("[bold yellow]⚠️  AI recommends splitting this story.[/bold yellow]")
        console.print(f"  • Reason: {split_data.get('reason', 'N/A')}")
        if est_loc or est_files:
            console.print(f"  • Estimated scope: ~{est_loc or '?'} LOC across {est_files or '?'} files")
        console.print(f"  • Suggestions: {len(split_data.get('suggestions', []))}")
        for i, s in enumerate(split_data.get("suggestions", []), 1):
            console.print(f"    {i}. {s}")
        console.print(f"\nDecomposition saved to: {plan_path}")
        console.print("[dim]Create child stories with: agent new-story <ID>[/dim]")
        raise typer.Exit(code=2)


# Re-export parse_split_request for handle_split_request
from agent.commands.runbook_helpers import parse_split_request  # noqa: E402
